class YouTubeContentDetector {
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
        // Upload elements
        this.uploadBox = document.getElementById('uploadBox');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfoCard = document.getElementById('fileInfoCard');
        this.fileName = document.getElementById('fileName');
        this.fileStats = document.getElementById('fileStats');
        this.removeBtn = document.getElementById('removeBtn');

        // Settings elements
        this.settingsPanel = document.getElementById('settingsPanel');
        this.audioThreshold = document.getElementById('audioThreshold');
        this.videoThreshold = document.getElementById('videoThreshold');
        this.gpuEnabled = document.getElementById('gpuEnabled');
        this.audioValue = document.getElementById('audioValue');
        this.videoValue = document.getElementById('videoValue');
        this.analyzeBtn = document.getElementById('analyzeBtn');

        // Progress elements
        this.progressCard = document.getElementById('progressCard');
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
        this.currentStep = document.getElementById('currentStep');
        this.elapsedTime = document.getElementById('elapsedTime');
        this.cancelBtn = document.getElementById('cancelBtn');

        // Results elements
        this.resultsContainer = document.getElementById('resultsContainer');
        this.totalVideos = document.getElementById('totalVideos');
        this.reuploadCount = document.getElementById('reuploadCount');
        this.reuploadPercent = document.getElementById('reuploadPercent');
        this.clusterCount = document.getElementById('clusterCount');
        this.exportBtn = document.getElementById('exportBtn');
    }

    attachEventListeners() {
        // Upload
        this.uploadBtn.addEventListener('click', () => this.fileInput.click());
        this.uploadBox.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        this.removeBtn.addEventListener('click', () => this.clearFile());

        // Drag and drop
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

        // Analysis
        this.analyzeBtn.addEventListener('click', () => this.startAnalysis());
        this.cancelBtn.addEventListener('click', () => this.cancelAnalysis());
        this.exportBtn.addEventListener('click', () => this.exportResults());
    }

    initSliders() {
        this.audioThreshold.addEventListener('input', (e) => {
            this.audioValue.textContent = `${Math.round(e.target.value * 100)}%`;
        });

        this.videoThreshold.addEventListener('input', (e) => {
            this.videoValue.textContent = `${Math.round(e.target.value * 100)}%`;
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

                // Show file info
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
        this.settingsPanel.style.display = 'none';
        this.progressCard.style.display = 'block';
        this.resultsContainer.style.display = 'none';

        this.startTime = Date.now();
        this.timerInterval = setInterval(() => this.updateTimer(), 1000);

        const config = {
            audioThreshold: parseFloat(this.audioThreshold.value),
            videoThreshold: parseFloat(this.videoThreshold.value),
            gpuEnabled: this.gpuEnabled.checked
        };

        console.log('Starting analysis with config:', config);

        try {
            await this.simulateProcessing();
            this.showResults();
        } catch (error) {
            alert('Lỗi trong quá trình xử lý');
            console.error(error);
            this.cancelAnalysis();
        }
    }

    async simulateProcessing() {
        const steps = [
            'Đang tải video từ YouTube...',
            'Trích xuất đặc trưng âm thanh...',
            'Trích xuất đặc trưng hình ảnh...',
            'Tính toán ma trận tương đồng...',
            'Phát hiện các cụm reupload...',
            'Tạo báo cáo kết quả...'
        ];

        for (let i = 0; i < steps.length; i++) {
            if (!this.isProcessing) break;

            this.currentStep.textContent = i + 1;
            this.progressText.textContent = steps[i];
            const progress = ((i + 1) / steps.length) * 100;
            this.progressBar.style.width = `${progress}%`;

            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    }

    showResults() {
        clearInterval(this.timerInterval);
        this.isProcessing = false;
        this.progressCard.style.display = 'none';
        this.resultsContainer.style.display = 'block';

        // Mock results
        const mockResults = {
            totalVideos: 150,
            reuploads: Math.floor(Math.random() * 30) + 10,
            clusters: Math.floor(Math.random() * 10) + 3
        };

        mockResults.percentage = ((mockResults.reuploads / mockResults.totalVideos) * 100).toFixed(1);

        this.totalVideos.textContent = mockResults.totalVideos;
        this.reuploadCount.textContent = mockResults.reuploads;
        this.reuploadPercent.textContent = `${mockResults.percentage}%`;
        this.clusterCount.textContent = mockResults.clusters;

        console.log('Analysis complete:', mockResults);
    }

    cancelAnalysis() {
        this.isProcessing = false;
        clearInterval(this.timerInterval);
        this.progressCard.style.display = 'none';
        this.settingsPanel.style.display = 'block';
    }

    exportResults() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const filename = `youtube_detection_results_${timestamp}.xlsx`;

        console.log('Exporting results:', filename);
        alert(`Đang xuất kết quả ra file: ${filename}\n\n(Chức năng này sẽ kết nối với backend API)`);
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

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new YouTubeContentDetector();
    console.log('YouTube Content Detector initialized');
});
