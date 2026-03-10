// UploadPage.jsx - where users upload their ZIP file of resumes
// handles drag and drop, file selection, upload to Flask, and shows results

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import '../styles/upload.css';

function UploadPage() {
    const navigate = useNavigate();
    const fileInputRef = useRef(null);

    // state for tracking the upload flow
    const [selectedFile, setSelectedFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState(null);
    const [error, setError] = useState(null);
    const [isDragOver, setIsDragOver] = useState(false);

    // this handles when a user drops a file onto the dropzone
    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragOver(false);
        setError(null);

        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.zip')) {
            setSelectedFile(file);
        } else {
            setError('Please upload a ZIP file.');
        }
    };

    // prevents the browser from opening the file when dragged over
    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragOver(true);
    };

    const handleDragLeave = () => {
        setIsDragOver(false);
    };

    // when the user clicks the dropzone, open the file picker
    const handleDropzoneClick = () => {
        fileInputRef.current.click();
    };

    // handles file selection from the file picker dialog
    const handleFileChange = (e) => {
        setError(null);
        const file = e.target.files[0];
        if (file && file.name.endsWith('.zip')) {
            setSelectedFile(file);
        } else if (file) {
            setError('Please upload a ZIP file.');
        }
    };

    // removes the selected file so the user can pick a different one
    const handleRemoveFile = () => {
        setSelectedFile(null);
        setError(null);
        // reset the file input so the same file can be selected again
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // sends the file to our Flask backend for processing
    const handleUpload = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        setError(null);

        // we use FormData because that's how you send files with axios
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            // posting to Flask backend - make sure Flask is running on port 5000
            const response = await axios.post('http://localhost:5001/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            console.log('upload response:', response.data);
            setUploadResult(response.data);
        } catch (err) {
            console.error('upload failed:', err);
            // try to show the server's error message if available
            const errorMsg =
                err.response?.data?.error || 'Something went wrong. Is the backend running?';
            setError(errorMsg);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="upload-page">
            <div className="upload-container">
                <h1 className="upload-title">Upload Resumes</h1>
                <p className="upload-subtitle">
                    Drop a ZIP file containing PDF or DOCX resumes to get started.
                </p>

                {/* show different content based on the current state */}
                {uploadResult ? (
                    // success state - upload is done
                    <div className="upload-success">
                        <span className="upload-success-icon">✅</span>
                        <h2 className="upload-success-title">Upload Complete!</h2>
                        <p className="upload-success-text">
                            {uploadResult.count} resume{uploadResult.count !== 1 ? 's' : ''} processed
                            successfully.
                        </p>
                        <button
                            className="btn-primary"
                            onClick={() => navigate('/dashboard')}
                        >
                            View Results on Dashboard
                        </button>
                    </div>
                ) : isUploading ? (
                    // loading state - file is being processed
                    <div className="upload-loading">
                        <div className="upload-spinner"></div>
                        <p className="upload-loading-text">Processing resumes...</p>
                    </div>
                ) : (
                    // default state - waiting for file
                    <>
                        {error && <div className="upload-error">⚠️ {error}</div>}

                        {/* the drag and drop zone */}
                        <div
                            className={`upload-dropzone ${isDragOver ? 'drag-over' : ''}`}
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onClick={handleDropzoneClick}
                        >
                            <span className="upload-dropzone-icon">📁</span>
                            <p className="upload-dropzone-text">
                                Drop your ZIP file here or <strong>click to browse</strong>
                            </p>
                        </div>

                        {/* hidden file input that gets triggered by clicking the dropzone */}
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="upload-file-input"
                            accept=".zip"
                            onChange={handleFileChange}
                        />

                        {/* show the selected file name */}
                        {selectedFile && (
                            <div className="upload-file-info">
                                <span className="upload-file-name">
                                    📎 {selectedFile.name}
                                </span>
                                <button
                                    className="upload-file-remove"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveFile();
                                    }}
                                >
                                    ✕
                                </button>
                            </div>
                        )}

                        {/* upload button - disabled until a file is selected */}
                        <button
                            className={`btn-primary upload-btn ${!selectedFile ? 'disabled' : ''}`}
                            onClick={handleUpload}
                            disabled={!selectedFile}
                        >
                            Upload & Analyze
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}

export default UploadPage;
