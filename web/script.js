class YouTubeContentDetector {
    constructor() {
        this.uploadedFile = null;
        this.isProcessing = false;
        this.startTime = null;
        this.timerInterval = null;
        this.jobId = null;

        this.initElements();
        this.attachEventListeners();
        this.initSliders();
    }

    initElements() {
        this.uploadBox = document.getElementById('uploadBox');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfoCard = document.getElementById('fileInfoCard');
        this.fileName = document.getElementById('fileName');
        this.fileStats = document.getElementById('fileStats');
        this.removeBtn = document.getElementById('removeBtn');

        this.settingsPanel = document.getElementById('settingsPanel');
        this.audioThreshold = document.getElementById('audioThreshold');
        this.videoThreshold = document.getElementById('videoThreshold');
        this.combinedThreshold = document.getElementById('combinedThreshold');
        this.gpuEnabled = document.getElementById('gpuEnabled');
        this.audioValue = document.getElementById('audioValue');
        this.videoValue = document.getElementById('videoValue');
        this.combinedValue = document.getElementById('combinedValue');
        this.analyzeBtn = document.getElementById('analyzeBtn');

        this.progressCard = document.getElementById('progressCard');
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
        this.currentStep = document.getElementById('currentStep');
        this.elapsedTime = document.getElementById('elapsedTime');
        this.cancelBtn = document.getElementById('cancelBtn');
        this.forceKillBtn = document.getElementById('forceKillBtn');

        this.resultsContainer = document.getElementById('resultsContainer');
        this.totalVideos = document.getElementById('totalVideos');
        this.reuploadCount = document.getElementById('reuploadCount');
        this.reuploadPercent = document.getElementById('reuploadPercent');
        this.clusterCount = document.getElementById('clusterCount');
        this.exportBtn = document.getElementById('exportBtn');

        this.tabBtns = document.querySelectorAll('.tab-btn');
        this.tabPanes = document.querySelectorAll('.tab-pane');
    }

    attachEventListeners() {
        this.uploadBtn.addEventListener('click', () => this.fileInput.click());
        this.uploadBox.addEventListener('click', (e) => {
            if (e.target === this.uploadBox || e.target.closest('.upload-icon-wrapper') || e.target.closest('h3') || e.target.closest('p')) {
                this.fileInput.click();
            }
        });
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        this.removeBtn.addEventListener('click', () => this.clearFile());

        this.uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadBox.classList.add('drag-over');
        });

        this.uploadBox.addEventListener('dragleave', () => {
            this.uploadBox.classList.remove('drag-over');
        });

        this.uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadBox.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });

        this.analyzeBtn.addEventListener('click', () => this.startAnalysis());
        this.cancelBtn.addEventListener('click', () => this.cancelAnalysis());
        this.forceKillBtn.addEventListener('click', () => this.forceKillServer());
        this.exportBtn.addEventListener('click', () => this.exportResults());

        this.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
    }

    initSliders() {
        this.audioThreshold.addEventListener('input', (e) => {
            this.audioValue.textContent = `${Math.round(e.target.value * 100)}%`;
        });

        this.videoThreshold.addEventListener('input', (e) => {
            this.videoValue.textContent = `${Math.round(e.target.value * 100)}%`;
        });

        this.combinedThreshold.addEventListener('input', (e) => {
            this.combinedValue.textContent = `${Math.round(e.target.value * 100)}%`;
        });
    }

    switchTab(tabName) {
        this.tabBtns.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        this.tabPanes.forEach(pane => {
            if (pane.dataset.pane === tabName) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }

    handleFile(file) {
        if (!file.name.match(/\.(xlsx|xls|csv)$/)) {
            alert('Vui lòng chọn file Excel (.xlsx, .xls) hoặc CSV');
            return;
        }

        this.uploadedFile = file;
        this.parseExcelFile(file);
    }

    parseExcelFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet);

                const videoCount = jsonData.length;
                const fileSize = this.formatFileSize(file.size);

                this.fileName.textContent = file.name;
                this.fileStats.textContent = `${videoCount} videos • ${fileSize}`;
                this.fileInfoCard.style.display = 'flex';
                this.settingsPanel.style.display = 'block';

                console.log(`File loaded: ${videoCount} videos`);
            } catch (error) {
                alert('Lỗi khi đọc file. Vui lòng kiểm tra định dạng file.');
                console.error(error);
            }
        };
        reader.readAsArrayBuffer(file);
    }

    clearFile() {
        this.uploadedFile = null;
        this.fileInfoCard.style.display = 'none';
        this.settingsPanel.style.display = 'none';
        this.fileInput.value = '';
    }

    async startAnalysis() {
        if (!this.uploadedFile || this.isProcessing) return;

        this.isProcessing = true;
        this.switchTab('compare');

        this.startTime = Date.now();
        this.timerInterval = setInterval(() => this.updateTimer(), 1000);

        const formData = new FormData();
        formData.append('file', this.uploadedFile);
        formData.append('audio_threshold', this.audioThreshold.value);
        formData.append('video_threshold', this.videoThreshold.value);
        formData.append('combined_threshold', this.combinedThreshold.value);
        formData.append('gpu_enabled', this.gpuEnabled.checked);

        try {
            this.progressText.textContent = 'Đang tải lên file và bắt đầu phân tích...';
            this.progressBar.style.width = '5%';
            this.currentStep.textContent = '1';

            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.jobId = result.job_id;
                this.isProcessing = false;
                clearInterval(this.timerInterval);
                this.showResults(result.results);
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (error) {
            const errorMsg = error.message || 'Unknown error';
            if (errorMsg.includes('cancelled') || errorMsg.includes('Cancelled')) {
                alert('Đã hủy phân tích');
            } else {
                alert('Lỗi khi phân tích: ' + errorMsg);
            }
            console.error(error);
            this.cancelAnalysis();
        }
    }

    async pollProgress() {
        // Không cần poll vì xử lý đồng bộ
    }

    updateProgress(progress) {
        const percent = Math.round(progress.percent || 0);
        this.progressBar.style.width = `${percent}%`;
        this.progressText.textContent = progress.message || 'Đang xử lý...';
        this.currentStep.textContent = `${progress.step || 0}/6`;
    }

    showResults(results) {
        this.switchTab('results');

        this.totalVideos.textContent = results.total_videos || 0;
        this.reuploadCount.textContent = results.reupload_count || 0;
        this.reuploadPercent.textContent = `${results.reupload_percent || 0}%`;
        this.clusterCount.textContent = results.cluster_count || 0;

        const statTotal = document.getElementById('statTotalVideos');
        const statReuploads = document.getElementById('statReuploads');
        if (statTotal) statTotal.textContent = results.total_videos || 0;
        if (statReuploads) statReuploads.textContent = results.reupload_count || 0;

        console.log('Analysis complete:', results);
    }

    async cancelAnalysis() {
        if (!confirm('Bạn có chắc muốn hủy phân tích? Tất cả tiến trình sẽ bị mất.')) {
            return;
        }

        console.log('Cancelling analysis...');
        this.progressText.textContent = 'Đang hủy... (đợi 3 giây)';
        this.cancelBtn.disabled = true;
        this.cancelBtn.textContent = 'Đang hủy...';

        // Show force kill button immediately
        this.forceKillBtn.style.display = 'block';
        this.showNotification('⚠️ Nếu không dừng, click "Force Kill Server"', 'warning');

        try {
            const response = await fetch('/api/cancel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                console.log('Cancellation request sent');
                this.progressText.textContent = 'Đã gửi yêu cầu hủy. Nếu vẫn chạy, click Force Kill.';
            } else {
                console.error('Cancellation failed:', result.error);
                this.showNotification('Lỗi khi hủy: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error canceling:', error);
            this.showNotification('Không thể hủy: ' + error.message, 'error');
        }

        // Don't reset immediately - keep showing force kill option
    }

    async forceKillServer() {
        if (!confirm('⚠️ CẢNH BÁO: Thao tác này sẽ DỪNG HOÀN TOÀN server!\n\nBạn sẽ phải khởi động lại bằng tay.\n\nBạn có chắc chắn muốn tiếp tục?')) {
            return;
        }

        this.progressText.textContent = '⚠️ Đang force kill server...';
        this.forceKillBtn.disabled = true;
        this.forceKillBtn.textContent = '⚠️ Đang kill...';

        try {
            const response = await fetch('/api/force-kill', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('✓ Server đã dừng. Vui lòng khởi động lại!', 'warning');

                // Alert user after 2 seconds
                setTimeout(() => {
                    alert('Server đã dừng hoàn toàn.\n\nVui lòng:\n1. Đóng terminal\n2. Chạy lại: python api_server.py');
                }, 2000);
            }
        } catch (error) {
            // Expected error - server killed itself
            this.showNotification('✓ Server đã dừng. Vui lòng khởi động lại!', 'warning');

            setTimeout(() => {
                alert('Server đã dừng hoàn toàn.\n\nVui lòng:\n1. Đóng terminal (Ctrl+C)\n2. Chạy lại: python api_server.py');
            }, 2000);
        } finally {
            this.isProcessing = false;
            clearInterval(this.timerInterval);
            this.forceKillBtn.style.display = 'none';
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: ${type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-weight: 500;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    async exportResults() {
        if (!this.jobId) {
            alert('Không có kết quả để xuất');
            return;
        }

        try {
            const response = await fetch(`/api/export/${this.jobId}`);
            const blob = await response.blob();

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `youtube_detection_${Date.now()}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            console.log('Results exported successfully');
        } catch (error) {
            alert('Lỗi khi xuất kết quả: ' + error.message);
            console.error(error);
        }
    }

    updateTimer() {
        if (!this.startTime) return;
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        this.elapsedTime.textContent = `${elapsed}s`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new YouTubeContentDetector();
    console.log('YouTube Content Detector initialized');
});
