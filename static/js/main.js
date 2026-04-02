// 主页面JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('analyzeForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const statusMessage = document.getElementById('statusMessage');
    
    // PDF上传相关
    const pdfUploadArea = document.getElementById('pdfUploadArea');
    const pdfFileInput = document.getElementById('pdfFileInput');
    const pdfFileList = document.getElementById('pdfFileList');
    const sourceNetwork = document.getElementById('sourceNetwork');
    const sourceUpload = document.getElementById('sourceUpload');
    const sourcePdfAssociation = document.getElementById('sourcePdfAssociation');
    const networkSourceSettings = document.getElementById('networkSourceSettings');
    const uploadSourceSettings = document.getElementById('uploadSourceSettings');
    const pdfAssociationSettings = document.getElementById('pdfAssociationSettings');
    let uploadedFiles = [];
    
    // PDF联想分析相关
    const pdfAssociationUploadArea = document.getElementById('pdfAssociationUploadArea');
    const pdfAssociationFileInput = document.getElementById('pdfAssociationFileInput');
    const pdfAssociationFileInfo = document.getElementById('pdfAssociationFileInfo');
    let pdfAssociationFile = null;
    
    // 检查必要的元素是否存在
    if (!form || !analyzeBtn || !statusMessage) {
        console.error('必要的表单元素未找到');
        return;
    }
    
    // 确保PDF上传区域初始状态正确
    if (uploadSourceSettings && sourceUpload) {
        uploadSourceSettings.style.display = sourceUpload.checked ? 'block' : 'none';
    } else if (uploadSourceSettings) {
        uploadSourceSettings.style.display = 'none';
    }
    
    // 显示消息函数（提前定义，供其他函数使用）
    function showMessage(message, type) {
        if (!statusMessage) return;
        statusMessage.textContent = message;
        statusMessage.className = 'status-message ' + type;
        statusMessage.style.display = 'block';
        
        // 3秒后自动隐藏成功消息
        if (type === 'success') {
            setTimeout(() => {
                if (statusMessage) {
                    statusMessage.style.display = 'none';
                }
            }, 3000);
        }
    }
    
    // 检查系统状态函数（提前定义）
    async function checkSystemStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (!data.api_configured) {
                showMessage('⚠️ 警告: API未配置，请在config/config.yaml中配置DeepSeek、Kimi或Qwen API密钥', 'error');
            }
        } catch (error) {
            console.error('Status check failed:', error);
        }
    }
    
    // 检查系统状态
    checkSystemStatus();
    
    // 切换来源类型（支持多选）
    function updateTopicVisibility() {
        const topicGroup = document.getElementById('topicGroup');
        const topicInput = document.getElementById('topic');
        const yearRangeGroup = document.getElementById('yearRangeGroup');
        
        if (!topicGroup || !topicInput) return;
        
        const useNetwork = sourceNetwork && sourceNetwork.checked;
        const useUpload = sourceUpload && sourceUpload.checked;
        const usePdfAssociation = sourcePdfAssociation && sourcePdfAssociation.checked;
        
        // 只有网络检索模式需要主题
        if (useNetwork) {
            // 网络检索模式（单独或混合模式）
            topicGroup.style.display = 'block';
            // 只有在纯网络检索模式时才要求主题
            if (!useUpload && !usePdfAssociation) {
                topicInput.required = true;
            } else {
                topicInput.required = false;
            }
        } else {
            // 仅上传模式（不需要主题）
            topicGroup.style.display = 'none';
            topicInput.required = false;
        }
        
        // 年份范围设置：只有网络检索模式需要
        if (yearRangeGroup) {
            if (useNetwork) {
                yearRangeGroup.style.display = 'block';
            } else {
                yearRangeGroup.style.display = 'none';
            }
        }
    }
    
    if (sourceNetwork && networkSourceSettings) {
        sourceNetwork.addEventListener('change', function() {
            networkSourceSettings.style.display = this.checked ? 'block' : 'none';
            const networkSourceDetails = document.getElementById('networkSourceDetails');
            if (networkSourceDetails) {
                networkSourceDetails.style.display = this.checked ? 'block' : 'none';
            }
            updateTopicVisibility();
        });
    }
    
    if (sourceUpload && uploadSourceSettings) {
        sourceUpload.addEventListener('change', function() {
            uploadSourceSettings.style.display = this.checked ? 'block' : 'none';
            updateTopicVisibility();
        });
    }
    
    if (sourcePdfAssociation && pdfAssociationSettings) {
        sourcePdfAssociation.addEventListener('change', function() {
            pdfAssociationSettings.style.display = this.checked ? 'block' : 'none';
            updateTopicVisibility();
        });
    }
    
    // 初始化时更新主题显示状态
    updateTopicVisibility();
    
    // PDF联想分析：根据选中的网络源动态显示/隐藏数量输入框
    function updateAssociationSourceCounts() {
        const arxivCheck = document.getElementById('associationArxivCheck');
        const ieeeCheck = document.getElementById('associationIeeeCheck');
        const pubmedCheck = document.getElementById('associationPubmedCheck');
        
        const arxivDiv = document.getElementById('associationArxivCountDiv');
        const ieeeDiv = document.getElementById('associationIeeeCountDiv');
        const pubmedDiv = document.getElementById('associationPubmedCountDiv');
        
        if (arxivDiv) arxivDiv.style.display = arxivCheck && arxivCheck.checked ? 'block' : 'none';
        if (ieeeDiv) ieeeDiv.style.display = ieeeCheck && ieeeCheck.checked ? 'block' : 'none';
        if (pubmedDiv) pubmedDiv.style.display = pubmedCheck && pubmedCheck.checked ? 'block' : 'none';
    }
    
    // 为所有联想分析的网络源复选框添加事件监听
    const associationCheckboxes = document.querySelectorAll('input[name="association_sources"]');
    associationCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateAssociationSourceCounts);
    });
    
    // 初始化时更新一次
    updateAssociationSourceCounts();
    
    // PDF联想分析文件上传处理
    if (pdfAssociationFileInput && pdfAssociationUploadArea) {
        pdfAssociationFileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && file.type === 'application/pdf') {
                pdfAssociationFile = file;
                if (pdfAssociationFileInfo) {
                    pdfAssociationFileInfo.style.display = 'block';
                    pdfAssociationFileInfo.innerHTML = `
                        <strong>已选择文件:</strong> ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)
                        <button type="button" onclick="document.getElementById('pdfAssociationFileInput').value=''; pdfAssociationFile=null; document.getElementById('pdfAssociationFileInfo').style.display='none';" style="margin-left: 8px; padding: 2px 8px; background: var(--danger-color); color: white; border: none; border-radius: 4px; cursor: pointer;">删除</button>
                    `;
                }
            } else {
                showMessage('请选择PDF文件', 'error');
            }
        });
        
        // 拖拽上传
        pdfAssociationUploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            pdfAssociationUploadArea.style.backgroundColor = 'var(--bg-hover)';
        });
        
        pdfAssociationUploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            pdfAssociationUploadArea.style.backgroundColor = '';
        });
        
        pdfAssociationUploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            pdfAssociationUploadArea.style.backgroundColor = '';
            const file = e.dataTransfer.files[0];
            if (file && file.type === 'application/pdf') {
                pdfAssociationFileInput.files = e.dataTransfer.files;
                pdfAssociationFile = file;
                if (pdfAssociationFileInfo) {
                    pdfAssociationFileInfo.style.display = 'block';
                    pdfAssociationFileInfo.innerHTML = `
                        <strong>已选择文件:</strong> ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)
                        <button type="button" onclick="document.getElementById('pdfAssociationFileInput').value=''; pdfAssociationFile=null; document.getElementById('pdfAssociationFileInfo').style.display='none';" style="margin-left: 8px; padding: 2px 8px; background: var(--danger-color); color: white; border: none; border-radius: 4px; cursor: pointer;">删除</button>
                    `;
                }
            } else {
                showMessage('请拖拽PDF文件', 'error');
            }
        });
    }
    
    // 网络检索来源选择
    const arxivCheck = document.getElementById('arxivCheck');
    const ieeeXploreCheck = document.getElementById('ieeeXploreCheck');
    const pubmedCheck = document.getElementById('pubmedCheck');
    const arxivSettings = document.getElementById('arxivSettings');
    const ieeeXploreSettings = document.getElementById('ieeeXploreSettings');
    const pubmedSettings = document.getElementById('pubmedSettings');
    
    if (arxivCheck && arxivSettings) {
        arxivCheck.addEventListener('change', function() {
            arxivSettings.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    if (ieeeXploreCheck && ieeeXploreSettings) {
        ieeeXploreCheck.addEventListener('change', function() {
            ieeeXploreSettings.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    if (pubmedCheck && pubmedSettings) {
        pubmedCheck.addEventListener('change', function() {
            pubmedSettings.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // 初始化显示状态
    if (networkSourceSettings) {
        networkSourceSettings.style.display = sourceNetwork && sourceNetwork.checked ? 'block' : 'none';
    }
    if (uploadSourceSettings) {
        uploadSourceSettings.style.display = sourceUpload && sourceUpload.checked ? 'block' : 'none';
    }
    const networkSourceDetails = document.getElementById('networkSourceDetails');
    if (networkSourceDetails) {
        networkSourceDetails.style.display = sourceNetwork && sourceNetwork.checked ? 'block' : 'none';
    }
    if (arxivSettings && arxivCheck) {
        arxivSettings.style.display = arxivCheck.checked ? 'block' : 'none';
    }
    if (ieeeXploreSettings && ieeeXploreCheck) {
        ieeeXploreSettings.style.display = ieeeXploreCheck.checked ? 'block' : 'none';
    }
    if (pubmedSettings && pubmedCheck) {
        pubmedSettings.style.display = pubmedCheck.checked ? 'block' : 'none';
    }
    
    // PDF拖拽上传
    if (pdfUploadArea) {
        pdfUploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('dragover');
        });
        
        pdfUploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('dragover');
        });
        
        pdfUploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files).filter(file => file.type === 'application/pdf');
            handlePDFFiles(files);
        });
    }
    
    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', function(e) {
            const files = Array.from(e.target.files).filter(file => file.type === 'application/pdf');
            handlePDFFiles(files);
        });
    }
    
    function handlePDFFiles(files) {
        if (!pdfFileList) return;
        
        files.forEach(file => {
            // 检查是否已存在
            if (uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                return;
            }
            
            uploadedFiles.push(file);
            addFileToList(file);
        });
        
        if (uploadedFiles.length > 0 && pdfFileList) {
            pdfFileList.style.display = 'block';
        }
    }
    
    function addFileToList(file) {
        if (!pdfFileList) return;
        
        const fileItem = document.createElement('div');
        fileItem.className = 'pdf-file-item';
        fileItem.innerHTML = `
            <span class="pdf-file-name">${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</span>
            <button type="button" class="pdf-file-remove" data-filename="${file.name}">删除</button>
        `;
        
        fileItem.querySelector('.pdf-file-remove').addEventListener('click', function() {
            const filename = this.getAttribute('data-filename');
            uploadedFiles = uploadedFiles.filter(f => f.name !== filename);
            fileItem.remove();
            
            if (uploadedFiles.length === 0 && pdfFileList) {
                pdfFileList.style.display = 'none';
            }
        });
        
        pdfFileList.appendChild(fileItem);
    }
    
    // 表单提交
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        
        // 获取来源类型（支持多选）
        const selectedSources = Array.from(document.querySelectorAll('input[name="source_type"]:checked')).map(cb => cb.value);
        
        if (selectedSources.length === 0) {
            showMessage('请至少选择一个论文来源', 'error');
            return;
        }
        
        // 检查条件
        const useNetwork = selectedSources.includes('network');
        const useUpload = selectedSources.includes('upload');
        const usePdfAssociation = selectedSources.includes('pdf_association');
        
        // 只有纯网络检索模式才需要主题
        if (useNetwork && !useUpload && !usePdfAssociation && !topic) {
            showMessage('使用网络检索时，请输入研究主题', 'error');
            return;
        }
        
        if (useUpload && uploadedFiles.length === 0) {
            showMessage('使用上传本地PDF分析时，请至少上传一个PDF文件', 'error');
            return;
        }
        
        if (usePdfAssociation && !pdfAssociationFile) {
            showMessage('使用上传PDF联想分析时，请上传一个PDF文件', 'error');
            return;
        }
        
        // 获取选择的AI模型（论文详细分析模型和综述生成模型）
        const paperAnalysisModel = document.getElementById('paperAnalysisModel').value;
        const reviewModel = document.getElementById('reviewModel').value;
        const reviewDetailLevel = document.getElementById('reviewDetailLevel') ? document.getElementById('reviewDetailLevel').value : '500';
        
        // 禁用按钮，显示加载状态
        analyzeBtn.disabled = true;
        analyzeBtn.querySelector('.btn-text').style.display = 'none';
        analyzeBtn.querySelector('.btn-loading').style.display = 'flex';
        
        // 隐藏之前的状态消息
        statusMessage.style.display = 'none';
        
        try {
            let uploadedPapers = [];
            let pdfAssociationFileId = null;
            
            // 如果使用上传模式，先上传PDF文件
            if (useUpload) {
                const uploadFormData = new FormData();
                uploadedFiles.forEach((file) => {
                    uploadFormData.append('pdf_files', file);
                });
                uploadFormData.append('topic', topic || '上传的论文');
                
                showMessage('正在上传并解析PDF文件...', 'info');
                
                const uploadResponse = await fetch('/api/upload-pdfs', {
                    method: 'POST',
                    body: uploadFormData
                });
                
                const uploadResult = await uploadResponse.json();
                
                if (!uploadResponse.ok) {
                    throw new Error(uploadResult.error || '上传失败');
                }
                
                uploadedPapers = uploadResult.papers;
                showMessage(`成功解析 ${uploadedPapers.length} 个PDF文件`, 'success');
            }
            
            // 如果使用PDF联想分析模式，先上传PDF文件
            if (usePdfAssociation && pdfAssociationFile) {
                const uploadFormData = new FormData();
                uploadFormData.append('pdf_files', pdfAssociationFile);
                uploadFormData.append('topic', topic || '上传的论文');
                uploadFormData.append('for_association', 'true');  // 标记这是用于联想分析的
                
                showMessage('正在上传PDF文件用于联想分析...', 'info');
                
                const uploadResponse = await fetch('/api/upload-pdfs', {
                    method: 'POST',
                    body: uploadFormData
                });
                
                const uploadResult = await uploadResponse.json();
                
                if (!uploadResponse.ok) {
                    throw new Error(uploadResult.error || '上传失败');
                }
                
                // 保存上传的PDF文件ID（用于后续联想分析）
                if (uploadResult.pdf_file_id) {
                    pdfAssociationFileId = uploadResult.pdf_file_id;
                } else if (uploadResult.papers && uploadResult.papers.length > 0) {
                    // 如果没有返回pdf_file_id，尝试从papers中获取
                    pdfAssociationFileId = uploadResult.papers[0].paper_id;
                }
                
                showMessage('PDF文件上传成功，准备进行联想分析...', 'success');
            }
            
            // 构建表单数据
            const formData = {
                topic: topic || '上传的论文',
                use_network: useNetwork,
                use_upload: useUpload,
                use_pdf_association: usePdfAssociation,
                pdf_association_file_id: pdfAssociationFileId,  // 添加PDF文件ID
                uploaded_papers: uploadedPapers,
                paper_analysis_model: paperAnalysisModel,
                review_model: reviewModel,
                review_detail_level: reviewDetailLevel
            };
            
            // 如果使用网络检索，添加相关参数
            if (useNetwork) {
                // 获取选中的网络检索来源
                const selectedNetworkSources = Array.from(document.querySelectorAll('input[name="sources"]:checked')).map(cb => cb.value);
                
                if (selectedNetworkSources.length === 0) {
                    showMessage('请至少选择一个网络检索来源', 'error');
                    analyzeBtn.disabled = false;
                    analyzeBtn.querySelector('.btn-text').style.display = 'inline';
                    analyzeBtn.querySelector('.btn-loading').style.display = 'none';
                    return;
                }
                
                const useAiKeywords = document.getElementById('useAiKeywords').checked;
                const startYear = document.getElementById('startYear').value;
                const endYear = document.getElementById('endYear').value;
                const sortBy = document.getElementById('sortBy').value;
                
                const source_counts = {};
                
                // arXiv设置
                if (selectedNetworkSources.includes('arxiv')) {
                    const arxivCountInput = document.querySelector('input[name="arxiv_count"]');
                    if (arxivCountInput) {
                        const count = parseInt(arxivCountInput.value);
                        source_counts['arxiv'] = (count && count > 0) ? count : 20;
                    } else {
                        source_counts['arxiv'] = 20;
                    }
                    const arxivFulltext = document.querySelector('input[name="arxiv_fulltext"]');
                    if (arxivFulltext && arxivFulltext.checked) {
                        source_counts['arxiv_fulltext'] = true;
                    }
                }
                
                // IEEE Xplore设置
                if (selectedNetworkSources.includes('ieee_xplore')) {
                    const ieeeXploreCountInput = document.querySelector('input[name="ieee_xplore_count"]');
                    if (ieeeXploreCountInput) {
                        const count = parseInt(ieeeXploreCountInput.value);
                        source_counts['ieee_xplore'] = (count && count > 0) ? count : 20;
                    } else {
                        source_counts['ieee_xplore'] = 20;
                    }
                }
                
                // PubMed 设置
                if (selectedNetworkSources.includes('pubmed')) {
                    const pubmedCountInput = document.querySelector('input[name="pubmed_count"]');
                    if (pubmedCountInput) {
                        const count = parseInt(pubmedCountInput.value);
                        source_counts['pubmed'] = (count && count > 0) ? count : 20;
                    } else {
                        source_counts['pubmed'] = 20;
                    }
                }
                
                formData.sources = selectedNetworkSources;
                formData.source_counts = source_counts;
                formData.use_ai_keywords = useAiKeywords;
                formData.start_year = startYear;
                formData.end_year = endYear;
                formData.sort_by = sortBy;
            }
            
            // 如果使用PDF联想分析，添加相关参数
            if (usePdfAssociation) {
                // 重点文献数量固定为10篇
                formData.key_references_count = 10;
                
                // 获取选中的拓展搜索来源
                const selectedAssociationSources = Array.from(document.querySelectorAll('input[name="association_sources"]:checked')).map(cb => cb.value);
                formData.association_sources = selectedAssociationSources;
                
                // 获取年份范围
                const associationStartYear = document.getElementById('associationStartYear') ? document.getElementById('associationStartYear').value : '2023';
                const associationEndYear = document.getElementById('associationEndYear') ? document.getElementById('associationEndYear').value : 'latest';
                formData.association_start_year = associationStartYear;
                formData.association_end_year = associationEndYear;
                
                // 获取各源数量设置（只收集选中的源）
                const association_source_counts = {};
                if (selectedAssociationSources.includes('arxiv')) {
                    const arxivCountInput = document.querySelector('input[name="association_arxiv_count"]');
                    if (arxivCountInput) {
                        const count = parseInt(arxivCountInput.value);
                        association_source_counts['arxiv'] = (count && count > 0) ? count : 10;
                    }
                }
                if (selectedAssociationSources.includes('ieee_xplore')) {
                    const ieeeCountInput = document.querySelector('input[name="association_ieee_count"]');
                    if (ieeeCountInput) {
                        const count = parseInt(ieeeCountInput.value);
                        association_source_counts['ieee_xplore'] = (count && count > 0) ? count : 10;
                    }
                }
                if (selectedAssociationSources.includes('pubmed')) {
                    const pubmedCountInput = document.querySelector('input[name="association_pubmed_count"]');
                    if (pubmedCountInput) {
                        const count = parseInt(pubmedCountInput.value);
                        association_source_counts['pubmed'] = (count && count > 0) ? count : 10;
                    }
                }
                formData.association_source_counts = association_source_counts;
            }
            
            await submitAnalysis(formData);
        } catch (error) {
            showMessage('操作失败: ' + error.message, 'error');
            analyzeBtn.disabled = false;
            analyzeBtn.querySelector('.btn-text').style.display = 'inline';
            analyzeBtn.querySelector('.btn-loading').style.display = 'none';
        }
    });
    
    async function submitAnalysis(formData) {
        try {
            showMessage('正在检索论文，请稍候...', 'info');
            
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            console.log('服务器响应:', data);
            
            if (!response.ok) {
                throw new Error(data.error || '检索失败');
            }
            
            // 保存论文数据到sessionStorage
            if (data.papers) {
                sessionStorage.setItem('papersData', JSON.stringify(data.papers));
            }
            
            // 检查必要的数据
            if (!data.temp_file) {
                console.error('服务器响应数据:', data);
                console.error('缺少temp_file字段');
                throw new Error('服务器未返回临时文件路径，无法跳转。响应数据: ' + JSON.stringify(data));
            }
            
            // 保存来源统计到sessionStorage（用于动态显示）
            if (data.source_stats) {
                sessionStorage.setItem('sourceStats', JSON.stringify(data.source_stats));
            }
            
            // 跳转到论文列表页面，传递数据
            const params = new URLSearchParams({
                topic: formData.topic || '上传的论文',
                temp_file: data.temp_file,
                total: data.total_count || (data.papers ? data.papers.length : 0),
                paper_analysis_model: formData.paper_analysis_model || 'deepseek-chat',
                review_model: formData.review_model || formData.paper_analysis_model || 'deepseek-chat',
                review_detail_level: formData.review_detail_level || '500'
            });
            
            // 确保跳转
            const targetUrl = `/papers?${params.toString()}`;
            console.log('准备跳转到:', targetUrl);
            console.log('跳转参数:', params.toString());
            console.log('temp_file值:', data.temp_file);
            
            // 使用setTimeout确保所有操作完成后再跳转
            setTimeout(() => {
                try {
                    window.location.href = targetUrl;
                } catch (e) {
                    console.error('跳转失败:', e);
                    showMessage('跳转失败: ' + e.message, 'error');
                }
            }, 100);
            
        } catch (error) {
            console.error('Error:', error);
            showMessage('检索失败: ' + error.message, 'error');
            
            // 恢复按钮
            analyzeBtn.disabled = false;
            analyzeBtn.querySelector('.btn-text').style.display = 'inline';
            analyzeBtn.querySelector('.btn-loading').style.display = 'none';
        }
    }
});
