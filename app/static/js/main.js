document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const dragArea = document.getElementById('drag-area');
    const browseBtn = document.getElementById('browse-btn');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    const fileName = document.getElementById('file-name');
    const uploadProgress = document.getElementById('upload-progress');
    const translationSection = document.getElementById('translation-section');
    const languageSearch = document.getElementById('language-search');
    const languageDropdown = document.getElementById('language-dropdown');
    const translateBtn = document.getElementById('translate-btn');
    const translationProgressContainer = document.getElementById('translation-progress-container');
    const progressIcon = document.getElementById('progress-icon');
    const progressStatus = document.getElementById('progress-status');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressDetails = document.getElementById('progress-details');
    const translationComplete = document.getElementById('translation-complete');
    const downloadBtn = document.getElementById('download-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');
    const viewTranslationBtn = document.getElementById('view-translation-btn');
    const resultsSection = document.getElementById('results-section');
    const backToTranslationBtn = document.getElementById('back-to-translation-btn');
    const pageSelector = document.getElementById('page-selector');
    const originalText = document.getElementById('original-text');
    const translatedText = document.getElementById('translated-text');

    // Variables
    let fileId = null;
    let pdfData = null;
    let selectedLanguage = null;
    let translationData = null;
    let languages = [];
    let websocket = null;
    let websocketReady = false;

    // Check API status
    checkApiStatus();

    // Fetch supported languages
    fetchLanguages();

    // Event Listeners
    browseBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        if (this.files[0]) {
            handleFile(this.files[0]);
        }
    });

    // Drag & Drop Events
    dragArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragArea.classList.add('active');
    });

    dragArea.addEventListener('dragleave', () => {
        dragArea.classList.remove('active');
    });

    dragArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragArea.classList.remove('active');
        
        if (e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // Language search and selection
    languageSearch.addEventListener('input', filterLanguages);
    languageSearch.addEventListener('focus', () => {
        showLanguageDropdown();
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (e.target !== languageSearch && e.target !== languageDropdown) {
            languageDropdown.classList.add('hidden');
        }
    });

    // Translate button
    translateBtn.addEventListener('click', startTranslation);

    // View translation button
    viewTranslationBtn.addEventListener('click', () => {
        translationComplete.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        displaySelectedPage();
    });

    // Back to translation button
    backToTranslationBtn.addEventListener('click', () => {
        resultsSection.classList.add('hidden');
        translationComplete.classList.remove('hidden');
    });

    // Page selector
    pageSelector.addEventListener('change', displaySelectedPage);

    // Functions
    async function checkApiStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (!data.translation_available) {
                // Create a warning banner
                const banner = document.createElement('div');
                banner.className = 'bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-6';
                banner.innerHTML = `
                    <div class="flex items-center">
                        <div class="py-1"><i class="fas fa-exclamation-triangle text-yellow-500 mr-3"></i></div>
                        <div>
                            <p class="font-bold">API Key Not Configured</p>
                            <p>OpenAI API key is not properly configured. PDF upload and text extraction will work, but translation functionality will not be available.</p>
                            <p class="mt-2 text-sm">Please set a valid OpenAI API key in the .env file and restart the server.</p>
                        </div>
                    </div>
                `;
                
                // Insert at the top of the main content
                const mainContent = document.querySelector('main');
                mainContent.insertBefore(banner, mainContent.firstChild);
            }
        } catch (error) {
            console.error('Error checking API status:', error);
        }
    }

    async function fetchLanguages() {
        try {
            const response = await fetch('/api/languages');
            const data = await response.json();
            languages = data.languages;
        } catch (error) {
            console.error('Error fetching languages:', error);
            showError('Failed to fetch supported languages. Please refresh the page and try again.');
        }
    }

    function handleFile(file) {
        if (!file.type.includes('pdf')) {
            showError('Please upload a PDF file');
            return;
        }

        // Display file name and show upload status
        fileName.textContent = file.name;
        uploadStatus.classList.remove('hidden');
        
        // Upload the file
        uploadPdf(file);
    }

    async function uploadPdf(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Upload failed');
            }

            const data = await response.json();
            fileId = data.file_id;
            pdfData = data;

            // Update UI
            uploadProgress.innerHTML = '<i class="fas fa-check-circle text-green-600 mr-2"></i><span>Upload complete</span>';
            translationSection.classList.remove('hidden');
            showLanguageDropdown();
        } catch (error) {
            uploadProgress.innerHTML = '<i class="fas fa-times-circle text-red-600 mr-2"></i><span>Upload failed</span>';
            console.error('Error uploading PDF:', error);
            showError(`Error uploading PDF: ${error.message}`);
        }
    }

    function showLanguageDropdown() {
        if (languages.length === 0) {
            return;
        }

        languageDropdown.innerHTML = '';
        
        languages.forEach(lang => {
            const item = document.createElement('div');
            item.className = 'px-4 py-2 hover:bg-indigo-50 cursor-pointer';
            item.textContent = lang;
            
            item.addEventListener('click', () => {
                languageSearch.value = lang;
                selectedLanguage = lang;
                languageDropdown.classList.add('hidden');
                translateBtn.disabled = false;
            });
            
            languageDropdown.appendChild(item);
        });
        
        languageDropdown.classList.remove('hidden');
    }

    function filterLanguages() {
        const searchTerm = languageSearch.value.toLowerCase();
        
        if (searchTerm === '') {
            showLanguageDropdown();
            return;
        }
        
        const filteredLanguages = languages.filter(lang => 
            lang.toLowerCase().includes(searchTerm)
        );
        
        languageDropdown.innerHTML = '';
        
        if (filteredLanguages.length === 0) {
            const noResult = document.createElement('div');
            noResult.className = 'px-4 py-2 text-gray-500';
            noResult.textContent = 'No languages found';
            languageDropdown.appendChild(noResult);
        } else {
            filteredLanguages.forEach(lang => {
                const item = document.createElement('div');
                item.className = 'px-4 py-2 hover:bg-indigo-50 cursor-pointer';
                item.textContent = lang;
                
                item.addEventListener('click', () => {
                    languageSearch.value = lang;
                    selectedLanguage = lang;
                    languageDropdown.classList.add('hidden');
                    translateBtn.disabled = false;
                });
                
                languageDropdown.appendChild(item);
            });
        }
        
        languageDropdown.classList.remove('hidden');
    }

    function setupWebSocket() {
        return new Promise((resolve, reject) => {
            // Close existing WebSocket if any
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.close();
            }
            
            // Create a new WebSocket connection
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws/translate/${fileId}`;
            
            websocket = new WebSocket(wsUrl);
            
            websocket.onopen = function() {
                console.log('WebSocket connection established');
                websocketReady = true;
                resolve(websocket);
            };
            
            websocket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                console.log('WebSocket message received:', data);
                
                // Handle different message types
                switch (data.status) {
                    case 'connected':
                        progressStatus.textContent = 'Connected. Preparing translation...';
                        break;
                        
                    case 'translating':
                        updateProgressBar(data.progress);
                        progressStatus.textContent = 'Translating...';
                        progressDetails.textContent = data.message;
                        break;
                        
                    case 'page_completed':
                        updateProgressBar(data.progress);
                        progressStatus.textContent = 'Translating...';
                        progressDetails.textContent = data.message;
                        break;
                        
                    case 'completed':
                        updateProgressBar(100);
                        progressStatus.textContent = 'Translation completed!';
                        progressIcon.className = 'fas fa-check-circle text-green-600 mr-2';
                        progressIcon.classList.remove('spinner');
                        
                        // Show complete section after a short delay
                        setTimeout(() => {
                            translationProgressContainer.classList.add('hidden');
                            translationComplete.classList.remove('hidden');
                            
                            // Set download links
                            downloadBtn.href = `${data.export_url.replace('format=md', 'format=pdf')}`;
                            downloadMdBtn.href = data.export_url;
                            
                            // Fetch the translation data to display
                            fetchTranslation();
                        }, 1000);
                        break;
                        
                    case 'error':
                        progressStatus.textContent = 'Error';
                        progressIcon.className = 'fas fa-times-circle text-red-600 mr-2';
                        progressIcon.classList.remove('spinner');
                        progressDetails.textContent = data.message;
                        progressDetails.classList.add('text-red-600');
                        break;
                }
            };
            
            websocket.onerror = function(error) {
                console.error('WebSocket error:', error);
                websocketReady = false;
                showError('Error connecting to translation service. Please try again.');
                reject(error);
            };
            
            websocket.onclose = function() {
                console.log('WebSocket connection closed');
                websocketReady = false;
            };
        });
    }

    function updateProgressBar(percentage) {
        // Update progress bar
        const roundedPercentage = Math.round(percentage);
        progressBarFill.style.width = `${roundedPercentage}%`;
        progressPercentage.textContent = `${roundedPercentage}%`;
    }

    async function startTranslation() {
        if (!fileId || !selectedLanguage) {
            return;
        }
        
        // Show translation progress
        translateBtn.disabled = true;
        translationProgressContainer.classList.remove('hidden');
        translationComplete.classList.add('hidden');
        
        // Reset progress UI
        progressStatus.textContent = 'Initializing translation...';
        progressIcon.className = 'fas fa-spinner spinner text-indigo-600 mr-2';
        progressPercentage.textContent = '0%';
        progressBarFill.style.width = '0%';
        progressDetails.textContent = 'Connecting to translation service...';
        progressDetails.classList.remove('text-red-600');
        
        try {
            // Setup WebSocket for real-time progress first
            await setupWebSocket();
            
            // Wait a moment to ensure WebSocket is fully established
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Now start the translation
            await translatePdf();
        } catch (error) {
            console.error('Error setting up translation:', error);
            progressStatus.textContent = 'Connection failed';
            progressIcon.className = 'fas fa-times-circle text-red-600 mr-2';
            progressIcon.classList.remove('spinner');
            progressDetails.textContent = 'Failed to establish connection to translation service.';
            progressDetails.classList.add('text-red-600');
            translateBtn.disabled = false;
        }
    }

    async function translatePdf() {
        if (!fileId || !selectedLanguage || !websocketReady) {
            console.error('Cannot translate: missing fileId, language, or WebSocket not ready');
            return;
        }
        
        // Start the translation process
        const formData = new FormData();
        formData.append('file_id', fileId);
        formData.append('target_language', selectedLanguage);
        
        try {
            // Send a test message through WebSocket
            websocket.send(JSON.stringify({
                action: 'start_translation',
                file_id: fileId,
                language: selectedLanguage
            }));
            
            const response = await fetch('/api/translate', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Translation failed');
            }
            
            translationData = await response.json();
            console.log('Translation completed:', translationData);
            
            // If WebSocket didn't trigger completion, handle it here
            if (translationProgressContainer.classList.contains('hidden') === false) {
                updateProgressBar(100);
                progressStatus.textContent = 'Translation completed!';
                progressIcon.className = 'fas fa-check-circle text-green-600 mr-2';
                progressIcon.classList.remove('spinner');
                
                setTimeout(() => {
                    translationProgressContainer.classList.add('hidden');
                    translationComplete.classList.remove('hidden');
                    
                    // Set download links
                    if (translationData.export_url) {
                        downloadBtn.href = `${translationData.export_url.replace('format=md', 'format=pdf')}`;
                        downloadMdBtn.href = translationData.export_url;
                    }
                    
                    // Populate page selector
                    populatePageSelector();
                }, 1000);
            }
            
        } catch (error) {
            // Handle error
            progressStatus.textContent = 'Translation failed';
            progressIcon.className = 'fas fa-times-circle text-red-600 mr-2';
            progressIcon.classList.remove('spinner');
            progressDetails.textContent = error.message;
            progressDetails.classList.add('text-red-600');
            
            translateBtn.disabled = false;
            console.error('Error translating PDF:', error);
            
            // Check if it's an API key error
            if (error.message.includes('API key')) {
                showError(`Translation failed: OpenAI API key is invalid or not configured properly. Please check your .env file and restart the server.`);
            } else {
                showError(`Translation failed: ${error.message}`);
            }
        }
    }

    async function fetchTranslation() {
        if (!fileId || !selectedLanguage) {
            return;
        }
        
        try {
            const response = await fetch(`/api/translate?file_id=${fileId}&target_language=${selectedLanguage}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch translation data');
            }
            
            translationData = await response.json();
            
            // Populate page selector
            populatePageSelector();
        } catch (error) {
            console.error('Error fetching translation:', error);
        }
    }

    function populatePageSelector() {
        pageSelector.innerHTML = '';
        
        if (!pdfData || !pdfData.pages) {
            return;
        }
        
        pdfData.pages.forEach(page => {
            const option = document.createElement('option');
            option.value = page.page_number;
            option.textContent = `Page ${page.page_number}`;
            pageSelector.appendChild(option);
        });
    }

    function displaySelectedPage() {
        const selectedPage = parseInt(pageSelector.value);
        
        if (!pdfData || !translationData) {
            return;
        }
        
        // Find original page content
        const originalPage = pdfData.pages.find(page => page.page_number === selectedPage);
        
        // Find translated page content
        const translatedPage = translationData.pages.find(page => page.page_number === selectedPage);
        
        // Display content
        if (originalPage) {
            originalText.textContent = originalPage.content;
        } else {
            originalText.textContent = 'No content available';
        }
        
        if (translatedPage) {
            translatedText.textContent = translatedPage.content;
        } else {
            translatedText.textContent = 'No translation available';
        }
    }

    function showError(message) {
        // Create error toast
        const toast = document.createElement('div');
        toast.className = 'fixed top-4 right-4 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded shadow-md z-50 max-w-md';
        toast.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <i class="fas fa-exclamation-circle text-red-500 mr-2"></i>
                    <span>${message}</span>
                </div>
                <button class="text-red-500 hover:text-red-700 ml-4">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Add close button functionality
        const closeBtn = toast.querySelector('button');
        closeBtn.addEventListener('click', () => {
            document.body.removeChild(toast);
        });
        
        // Add to body
        document.body.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 5000);
    }
});
