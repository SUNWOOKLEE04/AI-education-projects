# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image, UnidentifiedImageError
import io
import traceback
from flask_cors import CORS
import re

load_dotenv()

app = Flask(__name__)
CORS(app)

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable is not set.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("Google Gemini API configured successfully.")
    except Exception as e:
        print(f"ERROR: Failed to configure Google Gemini API: {e}")
        GEMINI_API_KEY = None

def generate_bandage_recommendations(analysis_text):
    """Generate bandage replacement recommendations based on wound analysis"""
    if not analysis_text or "Analysis failed" in analysis_text:
        return "Analysis unavailable, cannot provide recommendations."

    recommendations = []
    recommendations.append("Bandage Recommendations (based on 7.6x7.6cm standard):")
    
    text_lower = analysis_text.lower()
    
    # Size assessment
    size_match = re.search(r'approx\.?\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*cm', text_lower)
    if size_match:
        try:
            width = float(size_match.group(1))
            length = float(size_match.group(2))
            if width > 7.6 or length > 7.6:
                recommendations.append("• Size: Consider using multiple bandages or larger size")
            else:
                recommendations.append("• Size: Standard bandage should provide adequate coverage")
        except ValueError:
            recommendations.append("• Size: Unable to determine from analysis")
    else:
        recommendations.append("• Size: Verify coverage manually")

    # Drainage-based frequency
    if any(term in text_lower for term in ["severe", "heavy", "copious"]):
        recommendations.append("• Change frequency: 2-3 times daily due to heavy drainage")
        recommendations.append("• ⚠️ Consider medical evaluation for excessive drainage")
    elif any(term in text_lower for term in ["moderate"]):
        recommendations.append("• Change frequency: 1-2 times daily")
    elif any(term in text_lower for term in ["mild", "minimal"]):
        recommendations.append("• Change frequency: Once daily or as needed")
    elif any(term in text_lower for term in ["none", "dry"]):
        recommendations.append("• Change frequency: Every 1-2 days or as needed")
    else:
        recommendations.append("• Change frequency: Monitor and change when saturated")

    # Additional care notes
    if any(term in text_lower for term in ["infection", "pus", "purulent"]):
        recommendations.append("\n⚠️ WARNING: Possible signs of infection detected")
        recommendations.append("Seek immediate medical attention")
    
    if any(term in text_lower for term in ["necrotic", "black", "gangrene"]):
        recommendations.append("\n• Note: Necrotic tissue present - professional evaluation needed")

    recommendations.append("\n• General: Keep wound clean and dry between changes")
    
    return "\n".join(recommendations)

def assess_wound_severity(analysis_text):
    """Assess wound severity based on visual characteristics"""
    if not analysis_text or "Analysis failed" in analysis_text:
        return "Assessment unavailable"

    text_lower = analysis_text.lower()
    severity_indicators = []
    
    # Check for concerning features
    if any(term in text_lower for term in ["gangrene", "extensive", "bone", "deep"]):
        severity_indicators.append("High severity indicators present")
    elif any(term in text_lower for term in ["moderate", "partial", "drainage"]):
        severity_indicators.append("Moderate severity indicators")
    elif any(term in text_lower for term in ["superficial", "shallow", "minor"]):
        severity_indicators.append("Lower severity indicators")
    else:
        severity_indicators.append("Severity assessment unclear from visual analysis")

    disclaimer = ("\n\nIMPORTANT: This assessment is based solely on visual analysis "
                 "and should NOT replace professional medical evaluation. "
                 "Proper wound assessment requires clinical examination.")
    
    return "\n".join(severity_indicators) + disclaimer

def determine_visual_stage(analysis_text):
    """Determine visual characteristics for display purposes"""
    if not analysis_text:
        return "unknown"
        
    text_lower = analysis_text.lower()
    
    if "gangrene" in text_lower:
        return "severe"
    elif any(term in text_lower for term in ["black", "necrotic", "eschar"]):
        return "necrotic"
    elif any(term in text_lower for term in ["yellow", "slough"]):
        return "infected"
    elif any(term in text_lower for term in ["red", "pink", "granulation"]):
        return "healing"
    elif any(term in text_lower for term in ["intact", "healed"]):
        return "normal"
    else:
        return "unclear"

@app.route('/analyze', methods=['POST'])
def analyze_wound():
    if not GEMINI_API_KEY:
        return jsonify({"error": "Server configuration error"}), 500

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate file type
    allowed_types = {'png', 'jpg', 'jpeg', 'webp'}
    file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_extension not in allowed_types:
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(allowed_types)}"}), 400

    try:
        # Process image
        image_data = file.read()
        try:
            image = Image.open(io.BytesIO(image_data))
            print(f"Processing image: {image.format}, {image.size}")
        except UnidentifiedImageError:
            return jsonify({"error": "Invalid or corrupted image file"}), 400

        # Configure AI model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Analysis prompt
        prompt = """
**MEDICAL DISCLAIMER: This analysis is for educational purposes only and should NOT be used for medical diagnosis or treatment decisions. Always consult healthcare professionals.**

Analyze this wound image and provide a detailed visual description focusing on:

1. **Tissue Types**: Identify visible tissue (granulation, slough, eschar, necrotic tissue)
2. **Size**: Estimate dimensions in centimeters if possible
3. **Drainage**: Assess visible exudate amount and type
4. **Surrounding Skin**: Describe periwound condition
5. **Depth**: Estimate wound depth from visual appearance
6. **Complications**: Note any visual signs of concern

Provide objective observations only. Do not assign clinical grades or stages.
"""

        # Generate analysis
        response = model.generate_content([prompt, image])
        
        try:
            analysis_result = response.text
            print("Analysis completed successfully")
        except ValueError as e:
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                return jsonify({"error": "Analysis blocked due to safety settings"}), 400
            else:
                return jsonify({"error": "Analysis result unavailable"}), 500

        # Generate additional assessments
        recommendations = generate_bandage_recommendations(analysis_result)
        severity_assessment = assess_wound_severity(analysis_result)
        visual_stage = determine_visual_stage(analysis_result)

        return jsonify({
            "analysis": analysis_result,
            "recommendations": recommendations,
            "severity_assessment": severity_assessment,
            "visual_stage": visual_stage
        })

    except Exception as e:
        print(f"Server error: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error occurred"}), 500

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"error": "File size too large. Maximum: 16MB"}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"
    print("Starting wound analysis application...")
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)
