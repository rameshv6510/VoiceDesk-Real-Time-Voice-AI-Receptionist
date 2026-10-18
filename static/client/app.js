// WebRTC Browser Client for VoiceDesk
let pc = null;
let localStream = null;
let sessionId = null;

const startBtn = document.getElementById('start-btn');
const hangupBtn = document.getElementById('hangup-btn');
const statusText = document.getElementById('status-text');
const statusDot = document.querySelector('.status-dot');
const visualizer = document.getElementById('visualizer');
const latencyVal = document.getElementById('latency-val');
const turnsVal = document.getElementById('turns-val');
const messagesContainer = document.getElementById('messages');

let lastMessageSender = null;
let lastMessageText = null;
let lastMessageTime = 0;

function appendMessage(sender, text) {
    const now = Date.now();
    if (sender === lastMessageSender && text === lastMessageText && (now - lastMessageTime < 3000)) {
        return; // Ignore duplicate frame
    }
    lastMessageSender = sender;
    lastMessageText = text;
    lastMessageTime = now;

    const msg = document.createElement('div');
    msg.className = `msg ${sender}`;
    let label = 'AI Receptionist';
    if (sender === 'caller') label = 'Caller (You)';
    else if (sender === 'system') label = 'System';
    msg.innerHTML = `<strong>${label}:</strong> ${text}`;
    messagesContainer.appendChild(msg);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function startCall() {
    try {
        statusText.textContent = 'Requesting microphone access...';
        statusDot.className = 'status-dot connecting';
        startBtn.disabled = true;

        localStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        statusText.textContent = 'Connecting to VoiceDesk...';

        // Connect microphone to visualizer
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaStreamSource(localStream);
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            const dataArray = new Uint8Array(analyser.frequencyBinCount);

            function checkAudioLevel() {
                if (!localStream) return;
                analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                let avg = sum / dataArray.length;
                if (avg > 15) {
                    visualizer.classList.add('speaking');
                } else {
                    visualizer.classList.remove('speaking');
                }
                requestAnimationFrame(checkAudioLevel);
            }
            checkAudioLevel();
        } catch (e) {
            console.log('Audio metering not supported:', e);
        }

        pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });

        localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

        pc.ontrack = (event) => {
            console.log('Received remote track:', event.track.kind);
            const remoteAudio = document.getElementById('remote-audio');
            if (remoteAudio) {
                if (event.streams && event.streams[0]) {
                    remoteAudio.srcObject = event.streams[0];
                } else {
                    remoteAudio.srcObject = new MediaStream([event.track]);
                }
                remoteAudio.play().catch(e => console.warn('Audio play warning:', e));
            }
        };

        // Data channel for real-time latency & transcript frames
        const dataChannel = pc.createDataChannel('events');
        dataChannel.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'transcript') {
                    appendMessage(data.sender, data.text);
                } else if (data.type === 'latency') {
                    latencyVal.textContent = `${data.latency_ms} ms`;
                    turnsVal.textContent = `${data.turn}`;
                }
            } catch (e) {
                console.error('Error parsing data channel frame:', e);
            }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // Wait for ICE gathering to complete or send immediately
        await new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                };
                pc.addEventListener('icegatheringstatechange', checkState);
                setTimeout(resolve, 1500); // 1.5s max gathering timeout
            }
        });

        const response = await fetch('/api/offer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const detail = errData.detail || `Signaling failed with status ${response.status}`;
            throw new Error(detail);
        }

        const answer = await response.json();
        await pc.setRemoteDescription(new RTCSessionDescription(answer));

        statusText.textContent = 'Connected (Call in progress)';
        statusDot.className = 'status-dot connected';
        visualizer.classList.add('active');
        hangupBtn.disabled = false;
        messagesContainer.innerHTML = '';
        appendMessage('system', 'Call connected. Voice line is open!');

    } catch (err) {
        console.error('Failed to start call:', err);
        statusText.textContent = `Connection failed: ${err.message}`;
        statusDot.className = 'status-dot';
        startBtn.disabled = false;
        hangupBtn.disabled = true;
    }
}

function hangupCall() {
    if (pc) {
        pc.close();
        pc = null;
    }
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }

    statusText.textContent = 'Call ended';
    statusDot.className = 'status-dot';
    visualizer.classList.remove('active');
    startBtn.disabled = false;
    hangupBtn.disabled = true;
}

startBtn.addEventListener('click', startCall);
hangupBtn.addEventListener('click', hangupCall);
