class YouTubeReuploadDetector {
    constructor() {
        this.uploadedFile = null;
        this.isProcessing = false;
        this.startTime = null;
        this.timerInterval = null;

        this.initElements();
        this.attachEventListeners();
        this.initSliders();
    }

    initElements() {
        this.uploadZone = document.getElementById('uploadZone');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
        this.removeFileBtn = document.getElementById('removeFile');
        this.dataPreview = document.getElementById('dataPreview');
        this.totalVideos = document.getElementById('totalVideos');
        this.totalCodes = document.getElementById('totalCodes');

        this.audioThreshold = document.getElementById('audioThreshold');
        this.videoThreshold = document.getElementById('videoThreshold');
        this.combinedThreshold = document.getElementById('combinedThreshold');
        this.gpuEnabled = document.getElementById('gpuEnabled');

        this.startBtn = document.getElementById('startBtn');
        this.cancelBtn = document.getElementById('cancelBtn');

        this.progressSection = document.getElementById('progressSection');
        this.progressText = document.getElementById('progressText');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressFill = document.getElementById('progressFill');
        this.currentStep = document.getElementById('currentStep');
        this.elapsedTime = document.getElementById('elapsedTime');

        this.resultsSection = document.getElementById('resultsSection');
        this.resultTotalVideos = document.getElementById('resultTotalVideos');
        this.resultReuploads = document.getElementById('resultReuploads');
        this.resultPercentage = document.getElementById('resultPercentage');
        this.resultClusters = document.getElementById('resultClusters');
        this.exportBtn = document.getElementById('exportBtn');

        this.terminal = document.getElementById('terminal');
        this.clearLogsBtn = document.getElementById('clearLogsBtn');
        this.copyLogsBtn = document.getElementById('copyLogsBtn');

        this.statusBadge = document.getElementById('statusBadge');
    }

    attachEventListeners() {
        this.uploadZone.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        this.uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadZone.classList.add('drag-over');
        });

        this.uploadZone.addEventListener('dragleave', () => {
            this.uploadZone.classList.remove('drag-over');
        });

        this.uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadZone.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });

        this.removeFileBtn.addEventListener('click', () => this.clearFile());
        this.startBtn.addEventListener('click', () => this.startProcessing());
        this.cancelBtn.addEventListener('click', () => this.cancelProcessing());
        this.exportBtn.addEventListener('click', () => this.exportResults());
        this.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        this.copyLogsBtn.addEventListener('click', () => this.copyLogs());
    }

    initSliders() {
        const sliders = [
            { slider: this.audioThreshold, valueEl: document.getElementById('audioThresholdValue') },
            { slider: this.videoThreshold, valueEl: document.getElementById('videoThresholdValue') },
            { slider: this.combinedThreshold, valueEl: document.getElementById('combinedThresholdValue') }
        ];

        sliders.forEach(({ slider, valueEl }) => {
            slider.addEventListener('input', (e) => {
                const value = parseFloat(e.target.value);
                valueEl.textContent = `${Math.round(value * 100)}%`;
            });
        });
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }

    handleFile(file) {
        if (!file.name.match(/\.(xlsx|xls)$/)) {
            this.addLog('Lỗi: Vui lòng chọn file Excel (.xlsx hoặc .xls)', 'error');
            return;
        }

        this.uploadedFile = file;
        this.uploadZone.style.display = 'none';
        this.fileInfo.style.display = 'flex';
        this.fileName.textContent = file.name;
        this.fileSize.textContent = this.formatFileSize(file.size);
        this.startBtn.disabled = false;

        this.addLog(`File đã tải lên: ${file.name} (${this.formatFileSize(file.size)})`, 'success');

        this.parseExcelPreview(file);
    }

    parseExcelPreview(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet);

                const totalVideos = jsonData.length;
                const codes = new Set(jsonData.map(row => row.Code || row.code).filter(Boolean));
                const totalCodes = codes.size;

                this.totalVideos.textContent = totalVideos;
                this.totalCodes.textContent = totalCodes;
                this.dataPreview.style.display = 'block';

                this.addLog(`Phát hiện ${totalVideos} video trong ${totalCodes} Code`, 'success');
            } catch (error) {
                this.addLog('Lỗi khi đọc file Excel', 'error');
                console.error(error);
            }
        };
        reader.readAsArrayBuffer(file);
    }

    clearFile() {
        this.uploadedFile = null;
        this.fileInfo.style.display = 'none';
        this.dataPreview.style.display = 'none';
        this.uploadZone.style.display = 'block';
        this.fileInput.value = '';
        this.startBtn.disabled = true;
        this.addLog('Đã xóa file', 'warning');
    }

    async startProcessing() {
        if (!this.uploadedFile || this.isProcessing) return;

        this.isProcessing = true;
        this.startBtn.disabled = true;
        this.progressSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.updateStatus('processing', 'Đang xử lý...');

        this.startTime = Date.now();
        this.timerInterval = setInterval(() => this.updateTimer(), 1000);

        this.addLog('='.repeat(60));
        this.addLog('Bắt đầu phân tích...', 'success');
        this.addLog('='.repeat(60));

        const config = {
            audioThreshold: parseFloat(this.audioThreshold.value),
            videoThreshold: parseFloat(this.videoThreshold.value),
            combinedThreshold: parseFloat(this.combinedThreshold.value),
            gpuEnabled: this.gpuEnabled.checked
        };

        this.addLog(`Cấu hình: Audio=${Math.round(config.audioThreshold*100)}%, Video=${Math.round(config.videoThreshold*100)}%, Combined=${Math.round(config.combinedThreshold*100)}%`);
        this.addLog(`GPU: ${config.gpuEnabled ? 'Bật' : 'Tắt'}`);

        try {
            await this.simulateProcessing();
        } catch (error) {
            this.addLog(`Lỗi: ${error.message}`, 'error');
            this.isProcessing = false;
            this.updateStatus('error', 'Lỗi');
        }
    }

    async simulateProcessing() {
        const steps = [
            { name: 'Đang tải video từ YouTube...', duration: 3000 },
            { name: 'Trích xuất đặc trưng âm thanh...', duration: 2500 },
            { name: 'Trích xuất đặc trưng hình ảnh...', duration: 2500 },
            { name: 'Tính toán ma trận tương đồng...', duration: 2000 },
            { name: 'Phát hiện các cụm reupload...', duration: 2000 },
            { name: 'Tạo báo cáo kết quả...', duration: 1500 }
        ];

        for (let i = 0; i < steps.length; i++) {
            if (!this.isProcessing) break;

            const step = steps[i];
            this.currentStep.textContent = `${i + 1}/${steps.length}`;
            this.progressText.textContent = step.name;
            const progress = ((i + 1) / steps.length) * 100;
            this.progressPercent.textContent = `${Math.round(progress)}%`;
            this.progressFill.style.width = `${progress}%`;

            this.addLog(`Bước ${i + 1}/${steps.length}: ${step.name}`);

            await new Promise(resolve => setTimeout(resolve, step.duration));
        }

        if (this.isProcessing) {
            this.completeProcessing();
        }
    }

    completeProcessing() {
        clearInterval(this.timerInterval);
        this.isProcessing = false;

        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'block';
        this.updateStatus('success', 'Hoàn thành');

        const mockResults = {
            totalVideos: parseInt(this.totalVideos.textContent) || 50,
            reuploads: Math.floor(Math.random() * 15) + 5,
            clusters: Math.floor(Math.random() * 8) + 3
        };

        mockResults.percentage = ((mockResults.reuploads / mockResults.totalVideos) * 100).toFixed(1);

        this.resultTotalVideos.textContent = mockResults.totalVideos;
        this.resultReuploads.textContent = mockResults.reuploads;
        this.resultPercentage.textContent = `${mockResults.percentage}%`;
        this.resultClusters.textContent = mockResults.clusters;

        this.addLog('='.repeat(60));
        this.addLog('Hoàn thành phân tích!', 'success');
        this.addLog(`Tổng video: ${mockResults.totalVideos}`, 'success');
        this.addLog(`Video reupload: ${mockResults.reuploads}`, 'success');
        this.addLog(`Tỷ lệ: ${mockResults.percentage}%`, 'success');
        this.addLog(`Số cụm: ${mockResults.clusters}`, 'success');
        this.addLog('='.repeat(60));

        this.startBtn.disabled = false;
    }

    cancelProcessing() {
        if (!this.isProcessing) return;

        this.isProcessing = false;
        clearInterval(this.timerInterval);
        this.progressSection.style.display = 'none';
        this.updateStatus('ready', 'Sẵn sàng');
        this.startBtn.disabled = false;

        this.addLog('Đã hủy xử lý', 'warning');
    }

    exportResults() {
        this.addLog('Đang xuất kết quả ra file Excel...', 'success');

        setTimeout(() => {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
            const filename = `reupload_results_${timestamp}.xlsx`;
            this.addLog(`Đã xuất: ${filename}`, 'success');

            alert('Chức năng xuất kết quả sẽ kết nối với backend Python API');
        }, 500);
    }

    updateTimer() {
        if (!this.startTime) return;
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        this.elapsedTime.textContent = `${elapsed}s`;
    }

    updateStatus(status, text) {
        const statusDot = this.statusBadge.querySelector('.status-dot');
        const statusText = this.statusBadge.querySelector('span:last-child');

        statusText.textContent = text;

        const colors = {
            ready: '#10b981',
            processing: '#f59e0b',
            success: '#10b981',
            error: '#ef4444'
        };

        statusDot.style.background = colors[status] || colors.ready;
    }

    addLog(message, type = 'info') {
        const line = document.createElement('div');
        line.className = 'terminal-line';

        const prompt = document.createElement('span');
        prompt.className = 'terminal-prompt';
        prompt.textContent = '$';

        const text = document.createElement('span');
        text.className = `terminal-text terminal-${type}`;
        text.textContent = message;

        line.appendChild(prompt);
        line.appendChild(text);
        this.terminal.appendChild(line);

        this.terminal.scrollTop = this.terminal.scrollHeight;
    }

    clearLogs() {
        this.terminal.innerHTML = `
            <div class="terminal-line">
                <span class="terminal-prompt">$</span>
                <span class="terminal-text">YouTube Reupload Detector v1.3.0</span>
            </div>
            <div class="terminal-line">
                <span class="terminal-prompt">$</span>
                <span class="terminal-text">Logs đã được xóa</span>
            </div>
        `;
    }

    copyLogs() {
        const logs = Array.from(this.terminal.querySelectorAll('.terminal-text'))
            .map(el => el.textContent)
            .join('\n');

        navigator.clipboard.writeText(logs).then(() => {
            this.addLog('Đã copy logs vào clipboard', 'success');
        });
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
    new YouTubeReuploadDetector();
});
