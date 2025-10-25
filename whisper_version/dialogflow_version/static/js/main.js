const startButton = document.getElementById('startButton');
const sendButton = document.getElementById('sendButton');
const textInput = document.getElementById('textInput');
const status = document.getElementById('status');
const statusBadge = document.getElementById('statusBadge');
const conversationLog = document.getElementById('conversationLog');
const listeningIndicator = document.getElementById('listeningIndicator');

let sessionId = localStorage.getItem('lyrise_session_id') || null;
let doctorsList = [];
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

console.log('Initial session ID:', sessionId);

async function loadDoctors() {
    try {
        const response = await fetch('/doctors');
        const data = await response.json();
        doctorsList = data.doctors;
        updateWelcomeMessage();
    } catch (error) {
        console.error('Error loading doctors:', error);
    }
}

function updateWelcomeMessage() {
    const welcomeMsgContent = document.querySelector('.welcome-message .message-content');
    if (welcomeMsgContent) {
        welcomeMsgContent.innerHTML = `
            <p>Hello! I'm your medical assistant. I can help you:</p>
            <ul class="features-list">
                <li>📅 Book appointments with doctors</li>
                <li>❌ Cancel existing appointments</li>
                <li>🔍 Check available time slots</li>
            </ul>
            <p>Type your message or click the microphone button to start!</p>
        `;
    }

    const doctorsUl = document.getElementById('doctorsListUl');
    if (doctorsUl && doctorsList.length > 0) {
        const doctorsHTML = doctorsList.map(doc => 
            `<li>👨⚕️ <strong>${doc.name}</strong> - ${doc.specialty}</li>`
        ).join('');
        doctorsUl.innerHTML = doctorsHTML;
    }
}

function updateStatus(text, color = '#10b981') {
    status.textContent = text;
    const dot = statusBadge.querySelector('.status-dot');
    dot.style.background = color;
}

async function playAudio(text) {
    try {
        const response = await fetch('/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
    } catch (error) {
        console.error('TTS error:', error);
    }
}

function createMessageElement(sender, message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = sender === 'You' ? 'message-user' : 'message-bot';
    
    if (sender === 'You') {
        messageDiv.innerHTML = `
            <div class="user-avatar">U</div>
            <div class="message-bubble">${message}</div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="bot-avatar">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 5C13.66 5 15 6.34 15 8C15 9.66 13.66 11 12 11C10.34 11 9 9.66 9 8C9 6.34 10.34 5 12 5ZM12 19.2C9.5 19.2 7.29 17.92 6 15.98C6.03 13.99 10 12.9 12 12.9C13.99 12.9 17.97 13.99 18 15.98C16.71 17.92 14.5 19.2 12 19.2Z" fill="currentColor"/>
                </svg>
            </div>
            <div class="message-bubble">${message}</div>
        `;
    }
    
    return messageDiv;
}

function logMessage(sender, message) {
    const welcomeMsg = conversationLog.querySelector('.welcome-message');
    if (welcomeMsg && sender === 'You') {
        welcomeMsg.remove();
    }

    const messageElement = createMessageElement(sender, message);
    conversationLog.appendChild(messageElement);
    conversationLog.scrollTop = conversationLog.scrollHeight;
}

async function sendTextToBackend(text) {
    try {
        updateStatus('Processing...', '#f59e0b');
        
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: sessionId })
        });
        
        const data = await response.json();
        
        if (data.session_id) {
            sessionId = data.session_id;
            localStorage.setItem('lyrise_session_id', sessionId);
        }
        
        logMessage('Agent', data.reply);
        await playAudio(data.reply);
        updateStatus('Ready', '#10b981');
        
    } catch (error) {
        console.error('Error:', error);
        const errorMsg = "I'm having trouble connecting. Please try again.";
        logMessage('Agent', errorMsg);
        updateStatus('Error', '#ef4444');
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await transcribeAudio(audioBlob);
            stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        isRecording = true;
        updateStatus('Recording...', '#6366f1');
        listeningIndicator.classList.add('active');
        startButton.style.transform = 'scale(1.1)';
        startButton.querySelector('.button-text').textContent = 'Stop';
    } catch (error) {
        console.error('Microphone error:', error);
        updateStatus('Mic Error', '#ef4444');
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        updateStatus('Processing...', '#f59e0b');
        listeningIndicator.classList.remove('active');
        startButton.style.transform = 'scale(1)';
        startButton.querySelector('.button-text').textContent = 'Tap to Speak';
    }
}

async function transcribeAudio(audioBlob) {
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        const response = await fetch('/transcribe', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.text) {
            logMessage('You', data.text);
            await sendTextToBackend(data.text);
        } else {
            updateStatus('No speech detected', '#ef4444');
            setTimeout(() => updateStatus('Ready', '#10b981'), 2000);
        }
    } catch (error) {
        console.error('Transcription error:', error);
        updateStatus('Error', '#ef4444');
        setTimeout(() => updateStatus('Ready', '#10b981'), 2000);
    }
}

startButton.onclick = () => {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
};

textInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && textInput.value.trim()) {
        sendButton.click();
    }
});

sendButton.onclick = () => {
    const message = textInput.value.trim();
    if (message) {
        logMessage('You', message);
        sendTextToBackend(message);
        textInput.value = '';
    }
};

document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        startButton.click();
    }
});

loadDoctors();
