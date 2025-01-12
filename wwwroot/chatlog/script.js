document.addEventListener('DOMContentLoaded', () => {
    const chatlogDiv = document.getElementById('chatlog');
    const lineCountInput = document.getElementById('lineCount');
    const saveSettingsButton = document.getElementById('saveSettings');

    // Function to load and display chatlog
    function loadChatlog() {
        fetch('/chatlog/chatlog.json?lines=' + getLineCount())
            .then(response => response.json())
            .then(chatlogData => {
                chatlogDiv.innerHTML = '';
                chatlogData.forEach(log => {
                    const chatEntry = document.createElement('div');
                    chatEntry.classList.add('chat-entry');

                    const metaInfoDiv = document.createElement('div');
                    metaInfoDiv.classList.add('chat-entry-meta');
                    chatEntry.appendChild(metaInfoDiv);

                    const timestampSpan = document.createElement('span');
                    timestampSpan.classList.add('chat-entry-timestamp');
                    timestampSpan.textContent = new Date(log.timestamp * 1000).toLocaleString();
                    metaInfoDiv.appendChild(timestampSpan);

                    const speakerSpan = document.createElement('span');
                    speakerSpan.classList.add('chat-entry-speaker');
                    speakerSpan.textContent = log.speaker;
                    metaInfoDiv.appendChild(speakerSpan);

                    const messageSpan = document.createElement('span');
                    messageSpan.classList.add('chat-entry-message');
                    messageSpan.textContent = log.message;
                    chatEntry.appendChild(messageSpan);

                    chatlogDiv.appendChild(chatEntry);
                });

                // Apply line count limit
                applyLineCountLimit();

                // Scroll to bottom with a delay
                setTimeout(() => {
                    chatlogDiv.lastElementChild?.scrollIntoView({ behavior: 'auto' });
                    //chatlogDiv.scrollTop = chatlogDiv.scrollHeight;
                }, 50); 
            })
            .catch(error => {
                console.error('Error loading chatlog:', error);
                chatlogDiv.innerHTML = '<p>Error loading chatlog.</p>';
            });
    }

    // Function to apply line count limit
    function applyLineCountLimit() {
        const lineCount = parseInt(lineCountInput.value, 10) || 100;
        const chatEntries = chatlogDiv.querySelectorAll('.chat-entry');
        if (chatEntries.length > lineCount) {
            for (let i = 0; i < chatEntries.length - lineCount; i++) {
                chatEntries[i].remove();
            }
        }
    }

    // Load settings from local storage
    function loadSettings() {
        const savedLineCount = getLineCount();        
        if (savedLineCount !== null) {
            lineCountInput.value = savedLineCount;
        }
    }

    function getLineCount() {
        return localStorage.getItem('lineCount') || 100;
    }

    // Save settings to local storage
    function saveSettings() {
        localStorage.setItem('lineCount', lineCountInput.value);
        applyLineCountLimit();
        loadChatlog();
    }

    // Load chatlog on initial load
    loadChatlog();

    // Load settings from local storage
    loadSettings();

    // Event listeners
    saveSettingsButton.addEventListener('click', saveSettings);
    lineCountInput.addEventListener('change', applyLineCountLimit);
});
