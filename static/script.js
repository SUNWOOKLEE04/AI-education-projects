document.addEventListener('DOMContentLoaded', () => {
    const woundImageInput = document.getElementById('woundImage');
    const fileNameSpan = document.getElementById('fileName');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const imagePreview = document.getElementById('imagePreview');
    const previewPlaceholder = document.getElementById('previewPlaceholder');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsSection = document.getElementById('resultsSection');
    const analysisResultP = document.getElementById('analysisResult');
    const bandSuggestionP = document.getElementById('bandSuggestion');
    const wagnerGradeResultP = document.getElementById('wagnerGradeResult');
    const tissueStageTextElement = document.getElementById('tissueStageText');
    const scaleSegments = document.querySelectorAll('.scale-segment');

    let selectedFile = null;

    woundImageInput.addEventListener('change', (event) => {
        selectedFile = event.target.files[0];

        if (selectedFile) {
            if (!selectedFile.type.startsWith('image/')) {
                showAlert('Please select a valid image file (JPG, PNG, WEBP).');
                resetFileSelection();
                return;
            }

            if (selectedFile.size > 16 * 1024 * 1024) {
                showAlert('File size too large. Please select an image under 16MB.');
                resetFileSelection();
                return;
            }

            fileNameSpan.textContent = selectedFile.name;
            analyzeBtn.disabled = false;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                previewPlaceholder.style.display = 'none';
            };
            reader.readAsDataURL(selectedFile);

            clearResults();
        } else {
            resetFileSelection();
        }
    });

    analyzeBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            showAlert('Please select an image first.');
            return;
        }

        showLoading(true);
        analyzeBtn.disabled = true;

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const response = await fetch('http://127.0.0.1:5000/analyze', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                let errorMessage = `Server error: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    console.error('Error parsing response:', e);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            displayResults(data);

        } catch (error) {
            console.error('Analysis error:', error);
            displayError(error.message);
        } finally {
            showLoading(false);
            if (selectedFile) {
                analyzeBtn.disabled = false;
            }
        }
    });

    function resetFileSelection() {
        fileNameSpan.textContent = 'No file selected';
        analyzeBtn.disabled = true;
        imagePreview.style.display = 'none';
        previewPlaceholder.style.display = 'block';
        selectedFile = null;
        clearResults();
    }

    function clearResults() {
        resultsSection.style.display = 'none';
        analysisResultP.textContent = '-';
        bandSuggestionP.textContent = '-';
        wagnerGradeResultP.textContent = '-';
        tissueStageTextElement.textContent = 'AI Assessment Status: Pending...';
        scaleSegments.forEach(segment => {
            segment.classList.remove('active');
        });
    }

    function showLoading(show) {
        loadingIndicator.style.display = show ? 'block' : 'none';
        if (!show) {
            resultsSection.style.display = 'block';
        }
    }

    function displayResults(data) {
        analysisResultP.textContent = data.analysis || "Analysis could not be completed.";
        bandSuggestionP.textContent = data.recommendations || "No recommendations available.";
        wagnerGradeResultP.textContent = data.severity_assessment || "Severity assessment unavailable.";
        
        const visualStage = data.visual_stage || "unclear";
        updateVisualScale(visualStage);
        
        resultsSection.style.display = 'block';
    }

    function displayError(message) {
        analysisResultP.textContent = `Analysis failed: ${message}`;
        bandSuggestionP.textContent = '-';
        wagnerGradeResultP.textContent = '-';
        tissueStageTextElement.textContent = 'Could not determine status due to error.';
        
        scaleSegments.forEach(segment => segment.classList.remove('active'));
        resultsSection.style.display = 'block';
    }

    function updateVisualScale(stageKey) {
        scaleSegments.forEach(segment => {
            segment.classList.remove('active');
        });

        const activeSegment = document.querySelector(`.scale-segment[data-stage="${stageKey}"]`);
        let stageDescription = "Status Classification Pending...";

        if (activeSegment) {
            activeSegment.classList.add('active');
            stageDescription = activeSegment.getAttribute('title') || stageKey;
        } else {
            const unclearSegment = document.querySelector('.scale-segment[data-stage="unclear"]');
            if (unclearSegment) {
                unclearSegment.classList.add('active');
            }
            stageDescription = "Could not classify visual characteristics";
        }

        tissueStageTextElement.textContent = `AI Assessment: ${stageDescription}`;
    }

    function showAlert(message) {
        alert(message);
    }
});
