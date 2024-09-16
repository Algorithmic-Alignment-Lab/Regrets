window.confirmFinishExperiment = function() {
    if (confirm('Are you sure you want to finish the experiment?.')) {
        window.location.href = "/review";
    }
};

function triggerOption(button, value) {
    document.getElementById('regretValue').value = value;
    document.getElementById('regretForm').submit();
}

function activateInputs() {
    const buttons = ['noRegretBtn', 'noRememberBtn', 'regretBtn', 'skipBtn'];
    buttons.forEach(btnId => document.getElementById(btnId).disabled = false);

    document.addEventListener('keydown', function(event) {
        const keyMap = {
            "ArrowRight": "noRegretBtn",
            "ArrowLeft": "regretBtn",
            "ArrowUp": "noRememberBtn",
            "ArrowDown": "skipBtn"
        };
        if (keyMap[event.key]) {
            triggerOption(document.getElementById(keyMap[event.key]), keyMap[event.key].replace("Btn", ""));
        }
    });
}

function startCountdown() {
    const countdownCanvas = document.getElementById('countdown');
    const ctx = countdownCanvas.getContext('2d');
    const totalTime = 5000; // milliseconds
    const startTime = performance.now();

    function drawCountdown() {
        const elapsedTime = performance.now() - startTime;
        const progress = elapsedTime / totalTime;
        ctx.clearRect(0, 0, countdownCanvas.width, countdownCanvas.height);
        ctx.beginPath();
        ctx.arc(countdownCanvas.width / 2, countdownCanvas.height / 2, countdownCanvas.width / 2 - 2,
            -Math.PI / 2, (-Math.PI / 2) + (2 * Math.PI * progress), false);
        ctx.lineTo(countdownCanvas.width / 2, countdownCanvas.height / 2);
        ctx.fillStyle = '#76c7c0';
        ctx.fill();

        if (elapsedTime < totalTime) {
            requestAnimationFrame(drawCountdown);
        } else {
            activateInputs();
        }
    }

    requestAnimationFrame(drawCountdown);
}

document.addEventListener('DOMContentLoaded', function() {
    startCountdown();
});