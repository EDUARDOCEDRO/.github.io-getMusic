document.addEventListener('DOMContentLoaded', function() {
    const downloadForm = document.getElementById('downloadForm');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressStatus = document.getElementById('progressStatus');
    const downloadButton = document.getElementById('downloadButton');
    
    // Auto-dismiss flash messages
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    downloadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const youtubeUrl = document.getElementById('youtube_url').value;
        
        // Verificação adicional para playlists
        if (youtubeUrl.includes('list=') && !youtubeUrl.includes('watch?v=')) {
            addFlashMessage('error', 'Por favor, use a URL de um vídeo específico, não de uma playlist');
            return;
        }
        
        progressContainer.style.display = 'block';
        downloadButton.disabled = true;
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        progressStatus.textContent = 'Preparando download...';
        progressBar.classList.add('progress-bar-animated', 'progress-bar-striped');
        progressBar.style.backgroundColor = '';
        
        const progressInterval = setInterval(checkProgress, 1000);
        
        fetch('/', {
            method: 'POST',
            body: new FormData(downloadForm),
            headers: {
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || 'Erro no servidor') });
            }
            return response.json();
        })
        .then(data => {
            clearInterval(progressInterval);
            if(data.success) {
                progressStatus.textContent = 'Download completo!';
                progressBar.style.width = '100%';
                progressPercent.textContent = '100%';
                progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
                
                addFlashMessage('success', `Download completo: ${data.filename}`);
                addFlashMessage('success', 
                    `<a href="/downloads/${data.filename}" class="alert-link">Clique aqui para baixar</a>`);
            }
        })
        .catch(error => {
            clearInterval(progressInterval);
            progressStatus.textContent = 'Erro no download';
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
            progressBar.style.backgroundColor = '#7535dcff';
            addFlashMessage('error', error.message);
        })
        .finally(() => {
            downloadButton.disabled = false;
        });
        
        function checkProgress() {
            fetch('/progress')
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'downloading' || data.status === 'complete') {
                        const progress = Math.round(data.progress);
                        progressBar.style.width = progress + '%';
                        progressPercent.textContent = progress + '%';
                        
                        if(data.status === 'complete') {
                            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
                            progressStatus.textContent = 'Conversão finalizada!';
                        } else {
                            progressStatus.textContent = 'Download em progresso...';
                        }
                    } else if(data.status === 'error') {
                        clearInterval(progressInterval);
                        progressStatus.textContent = 'Erro no download';
                        progressBar.style.backgroundColor = '#9435dcff';
                        progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
                        addFlashMessage('error', data.error || 'Erro desconhecido');
                        downloadButton.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Erro ao verificar progresso:', error);
                });
        }
    });
    
    function addFlashMessage(type, message) {
        const flashesDiv = document.querySelector('.flashes') || createFlashesDiv();
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        flashesDiv.prepend(alertDiv);
        
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }, 5000);
    }
    
    function createFlashesDiv() {
        const div = document.createElement('div');
        div.className = 'flashes';
        document.body.prepend(div);
        return div;
    }
});