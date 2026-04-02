// 论文列表页面JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    // 从URL参数获取数据
    const params = new URLSearchParams(window.location.search);
    const topic = params.get('topic');
    const tempFile = params.get('temp_file');
    const totalCount = params.get('total');
    
    // 显示主题
    document.getElementById('topicName').textContent = topic || '未知主题';
    
    // 显示统计信息（动态加载）
    document.getElementById('totalPapers').textContent = totalCount || '0';
    
    // 动态加载论文来源统计和论文列表
    if (tempFile) {
        loadSourceStats(tempFile);
        // 如果URL中有task_id，尝试加载详细信息
        const taskId = params.get('task_id');
        loadPapers(tempFile, taskId);
    }
    
    // 分析按钮点击事件
    const analyzeBtn = document.getElementById('analyzeBtn');
    const progressSection = document.getElementById('progressSection');
    let progressInterval = null;
    
    analyzeBtn.addEventListener('click', async function() {
        if (!tempFile) {
            showMessage('论文数据不存在，请返回重新检索', 'error');
            return;
        }
        
        // 禁用按钮，显示加载状态
        analyzeBtn.disabled = true;
        analyzeBtn.querySelector('.btn-text').style.display = 'none';
        analyzeBtn.querySelector('.btn-loading').style.display = 'flex';
        
        // 显示进度条
        progressSection.style.display = 'block';
        progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // 初始化进度
        updateProgress(0, 1, '正在启动分析...');
        
        try {
            // 获取批量大小设置
            const batchSizeSelect = document.getElementById('batchSize');
            const batchSize = batchSizeSelect ? parseInt(batchSizeSelect.value) : 1;
            
            // 获取综述详细程度
            const reviewDetailLevel = params.get('review_detail_level') || '500';
            
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    topic: topic,
                    temp_file: tempFile,
                    paper_analysis_model: params.get('paper_analysis_model') || params.get('ai_model') || 'deepseek-chat',  // 论文详细分析模型
                    review_model: params.get('review_model') || params.get('paper_analysis_model') || params.get('ai_model') || 'deepseek-chat',  // 综述生成模型
                    batch_size: batchSize,  // 批量阅读大小
                    review_detail_level: reviewDetailLevel  // 综述详细程度
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || '分析失败');
            }
            
            // 获取任务ID并开始轮询进度
            const taskId = data.task_id;
            startProgressPolling(taskId, topic, tempFile);
            
        } catch (error) {
            console.error('Error:', error);
            showMessage('分析失败: ' + error.message, 'error');
            
            // 恢复按钮
            analyzeBtn.disabled = false;
            analyzeBtn.querySelector('.btn-text').style.display = 'inline';
            analyzeBtn.querySelector('.btn-loading').style.display = 'none';
            progressSection.style.display = 'none';
        }
    });
    
    // 开始轮询进度
    function startProgressPolling(taskId, topic, tempFile) {
        progressInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/analyze/progress/${taskId}`);
                const progress = await response.json();
                
                // 准备进度数据
                const progressData = {
                    current_paper: progress.current_paper,
                    total_papers: progress.total_papers,
                    current_paper_title: progress.current_paper_title || ''  // 添加论文标题
                };
                
                updateProgress(
                    progress.progress || 0,
                    progress.step || 1,
                    progress.message || '处理中...',
                    progressData
                );
                
                if (progress.status === 'completed') {
                    clearInterval(progressInterval);
                    updateProgress(100, 4, '分析完成！', progressData);
                    
                    // 更新论文列表，显示分析结果
                    if (progress.result && progress.result.paper_details) {
                        // 重新加载论文列表，包含详细信息
                        loadPapersWithDetails(tempFile, taskId);
                    }
                    
                    // 等待2秒后跳转（让用户看到更新后的论文列表）
                    setTimeout(() => {
                        const resultParams = new URLSearchParams({
                            topic: topic,
                            temp_file: tempFile
                        });
                        
                        // 将结果数据存储到sessionStorage
                        sessionStorage.setItem('analysisResult', JSON.stringify(progress.result));
                        
                        // 保存task_id以便问答使用
                        sessionStorage.setItem('currentTaskId', taskId);
                        
                        // 将task_id添加到URL参数
                        resultParams.append('task_id', taskId);
                        
                        window.location.href = `/results?${resultParams.toString()}`;
                    }, 2000);
                } else if (progress.status === 'error') {
                    clearInterval(progressInterval);
                    showMessage(progress.message || '分析失败', 'error');
                    analyzeBtn.disabled = false;
                    analyzeBtn.querySelector('.btn-text').style.display = 'inline';
                    analyzeBtn.querySelector('.btn-loading').style.display = 'none';
                }
            } catch (error) {
                console.error('Progress polling error:', error);
            }
        }, 500); // 每0.5秒轮询一次，更流畅
    }
    
    // 更新进度显示
    function updateProgress(percent, step, message, progressData) {
        // 更新进度条
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const progressMessage = document.getElementById('progressMessage');
        
        if (progressFill) progressFill.style.width = percent + '%';
        if (progressText) progressText.textContent = Math.round(percent) + '%';
        
        // 显示详细消息
        let displayMessage = message;
        if (progressData && progressData.current_paper && progressData.total_papers) {
            // 如果有论文标题，显示标题
            if (progressData.current_paper_title) {
                const titleShort = progressData.current_paper_title.length > 60 
                    ? progressData.current_paper_title.substring(0, 60) + '...' 
                    : progressData.current_paper_title;
                displayMessage = `${message}（第 ${progressData.current_paper}/${progressData.total_papers} 篇）\n📄 ${titleShort}`;
            } else {
                // 改进显示：不显示20/20这种，而是显示"第X篇，共Y篇"
                if (progressData.current_paper === progressData.total_papers && progressData.total_papers > 1) {
                    displayMessage = `${message}（已完成 ${progressData.total_papers} 篇）`;
                } else if (progressData.current_paper > 0) {
                    displayMessage = `${message}（第 ${progressData.current_paper} 篇，共 ${progressData.total_papers} 篇）`;
                } else {
                    displayMessage = `${message}（共 ${progressData.total_papers} 篇）`;
                }
            }
        }
        if (progressMessage) {
            // 支持多行显示
            progressMessage.innerHTML = displayMessage.replace(/\n/g, '<br>');
        }
        
        // 更新步骤状态
        const steps = document.querySelectorAll('.progress-step');
        steps.forEach((stepEl, index) => {
            const stepNum = index + 1;
            stepEl.classList.remove('active', 'completed');
            
            if (stepNum < step) {
                stepEl.classList.add('completed');
            } else if (stepNum === step) {
                stepEl.classList.add('active');
            }
        });
    }
    
    // 加载论文来源统计
    async function loadSourceStats(tempFile) {
        try {
            const response = await fetch(`/api/get-papers?temp_file=${encodeURIComponent(tempFile)}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || '加载失败');
            }
            
            // 统计各来源的论文数量
            const sourceCounts = {};
            if (data.papers) {
                data.papers.forEach(paper => {
                    const source = paper.source.toLowerCase();
                    sourceCounts[source] = (sourceCounts[source] || 0) + 1;
                });
            }
            
            // 动态显示来源统计
            displaySourceStats(sourceCounts);
            
        } catch (error) {
            console.error('Error loading source stats:', error);
        }
    }
    
    // 显示来源统计（动态生成）
    function displaySourceStats(sourceCounts) {
        const statsGrid = document.querySelector('.stats-grid');
        if (!statsGrid) return;
        
        // 来源名称映射（仅 arXiv 和 IEEE Xplore）
        const sourceNames = {
            'ieee_xplore': { name: 'IEEE Xplore', icon: '🔬' },
            'arxiv': { name: 'arXiv', icon: '📄' },
            'pubmed': { name: 'PubMed', icon: '🧬' },
            'uploaded': { name: '上传的PDF', icon: '📤' }
        };
        
        // 清空现有统计（除了总数）
        const totalItem = statsGrid.querySelector('.stat-item:first-child');
        statsGrid.innerHTML = '';
        
        // 添加总数
        // 优先使用URL参数中的total（来自后端返回的total_count，已经包含了所有论文）
        const urlTotal = params.get('total');
        const calculatedTotal = Object.values(sourceCounts).reduce((a, b) => a + b, 0);
        // 使用URL参数中的total（如果存在且有效），否则使用计算的总数
        const finalTotal = (urlTotal && parseInt(urlTotal) > 0) ? parseInt(urlTotal) : calculatedTotal;
        
        if (totalItem) {
            // 更新现有的总数显示
            const totalValueElement = totalItem.querySelector('#totalPapers') || totalItem.querySelector('.stat-value');
            if (totalValueElement) {
                totalValueElement.textContent = finalTotal;
            }
            statsGrid.appendChild(totalItem);
        } else {
            const totalDiv = document.createElement('div');
            totalDiv.className = 'stat-item';
            totalDiv.innerHTML = `
                <div class="stat-value" id="totalPapers">${finalTotal}</div>
                <div class="stat-label">总论文数</div>
            `;
            statsGrid.appendChild(totalDiv);
        }
        
        // 同时更新页面顶部显示的总数
        const topTotalElement = document.getElementById('totalPapers');
        if (topTotalElement && topTotalElement !== statsGrid.querySelector('#totalPapers')) {
            topTotalElement.textContent = finalTotal;
        }
        
        // 动态添加各来源统计
        for (const [source, count] of Object.entries(sourceCounts)) {
            if (count > 0) {
                const sourceInfo = sourceNames[source] || { name: source.toUpperCase(), icon: '📄' };
                const sourceDiv = document.createElement('div');
                sourceDiv.className = 'stat-item';
                sourceDiv.innerHTML = `
                    <div class="stat-value">${count}</div>
                    <div class="stat-label">${sourceInfo.icon} ${sourceInfo.name}</div>
                `;
                statsGrid.appendChild(sourceDiv);
            }
        }
    }
    
    // 加载论文列表
    async function loadPapers(tempFile, taskId = null) {
        try {
            let url = `/api/get-papers?temp_file=${encodeURIComponent(tempFile)}`;
            if (taskId) {
                url += `&task_id=${encodeURIComponent(taskId)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || '加载失败');
            }
            
            // 保存到sessionStorage以便后续使用
            if (data.papers) {
                sessionStorage.setItem('papersData', JSON.stringify(data.papers));
            }
            if (data.paper_details) {
                sessionStorage.setItem('paperDetails', JSON.stringify(data.paper_details));
            }
            
            displayPapers(data.papers || [], data.paper_details || null);
            
        } catch (error) {
            console.error('Error loading papers:', error);
            // 尝试从sessionStorage获取
            const savedPapers = sessionStorage.getItem('papersData');
            const savedDetails = sessionStorage.getItem('paperDetails');
            if (savedPapers) {
                displayPapers(JSON.parse(savedPapers), savedDetails ? JSON.parse(savedDetails) : null);
            } else {
                showMessage('加载论文列表失败: ' + error.message, 'error');
            }
        }
    }
    
    // 加载论文列表（包含详细信息）- 直接调用loadPapers
    const loadPapersWithDetails = loadPapers;
    
    // 显示论文列表
    function displayPapers(papers, paperDetails = null) {
        const papersList = document.getElementById('papersList');
        
        if (!papers || papers.length === 0) {
            papersList.innerHTML = '<p>没有找到论文</p>';
            return;
        }
        
        // 创建paper_id到详细信息的映射
        const detailsMap = {};
        if (paperDetails && Array.isArray(paperDetails)) {
            paperDetails.forEach(detail => {
                if (detail.paper_id) {
                    detailsMap[detail.paper_id] = detail;
                }
            });
        }
        
        papersList.innerHTML = papers.map((paper, index) => {
            const detail = detailsMap[paper.paper_id] || null;
            // 获取论文类型（只在有分析结果时显示）
            // 如果detail存在且有paper_type，说明已经分析过，可以显示分类
            const paperType = detail?.paper_type || paper.paper_type || null;
            let paperTypeBadge = '';
            if (paperType) {
                const paperTypeLabel = paperType === 'review' ? '📚 综述' : '🔬 方法论';
                const paperTypeClass = paperType === 'review' ? 'paper-type-review' : 'paper-type-method';
                paperTypeBadge = `<span class="paper-type-badge ${paperTypeClass}">${paperTypeLabel}</span>`;
            }
            
            // 获取推荐阅读程度（星级，只在有分析结果时显示）
            const recScore = detail?.recommendation_score || (detail ? paper.recommendation_score : null);
            let starDisplay = '';
            if (recScore !== null && recScore !== undefined && detail) {
                const stars = '⭐'.repeat(recScore) + '☆'.repeat(5 - recScore);
                starDisplay = `<span class="recommendation-stars" title="推荐阅读程度：${recScore}星">${stars}</span>`;
            }
            
            const hasDetails = detail && (
                detail.q1_background || detail.q2_implementation || detail.q3_result ||
                detail.q4_modules || detail.q5_related_work || detail.q6_evaluation ||
                detail.q7_comparison || detail.q8_summary
            );
            
            // 构建悬停提示内容
            let tooltipContent = '';
            if (hasDetails) {
                tooltipContent = `
                    <div class="paper-detail-tooltip">
                        <h5>AI分析结果</h5>
                        <div class="detail-questions">
                            ${detail.q1_background ? `<div class="detail-item"><strong>1. 研究方向背景：</strong><p>${detail.q1_background}</p></div>` : ''}
                            ${detail.q2_implementation ? `<div class="detail-item"><strong>2. 实现内容：</strong><p>${detail.q2_implementation}</p></div>` : ''}
                            ${detail.q3_result ? `<div class="detail-item"><strong>3. 结果：</strong><p>${detail.q3_result}</p></div>` : ''}
                            ${detail.q4_modules ? `<div class="detail-item"><strong>4. 方法模块：</strong><p>${detail.q4_modules}</p></div>` : ''}
                            ${detail.q5_related_work ? `<div class="detail-item"><strong>5. 相关工作：</strong><p>${detail.q5_related_work}</p></div>` : ''}
                            ${detail.q6_evaluation ? `<div class="detail-item"><strong>6. 评估：</strong><p>${detail.q6_evaluation}</p></div>` : ''}
                            ${detail.q7_comparison ? `<div class="detail-item"><strong>7. 对比方法：</strong><p>${detail.q7_comparison}</p></div>` : ''}
                            ${detail.q8_summary ? `<div class="detail-item"><strong>8. 方法总结：</strong><p>${detail.q8_summary}</p></div>` : ''}
                        </div>
                    </div>
                `;
            } else {
                tooltipContent = `
                    <div class="paper-detail-tooltip">
                        <p style="color: #999;">该论文尚未进行AI分析，请先完成分析。</p>
                    </div>
                `;
            }
            
            return `
            <div class="paper-item-detailed">
                <div class="paper-number">#${index + 1}</div>
                <div class="paper-content">
                    <div class="paper-header">
                        <h4>${paper.title}</h4>
                        ${hasDetails ? `
                            <div class="paper-detail-wrapper">
                                <button class="paper-detail-btn" title="查看AI分析结果">📋</button>
                                ${tooltipContent}
                            </div>
                        ` : ''}
                    </div>
                    <div class="paper-meta">
                        ${paperTypeBadge}
                        ${starDisplay}
                        <span class="source-badge source-${paper.source}">${paper.source.toUpperCase()}</span>
                        ${paper.citation_count ? `<span class="citation-badge">📊 ${paper.citation_count} 次引用</span>` : ''}
                    </div>
                    <div class="paper-authors">
                        <strong>作者:</strong> ${paper.authors.slice(0, 5).join(', ')}${paper.authors.length > 5 ? ' 等' : ''}
                    </div>
                    <div class="paper-abstract">
                        <strong>摘要:</strong> ${paper.abstract.substring(0, 200)}${paper.abstract.length > 200 ? '...' : ''}
                    </div>
                    <div class="paper-actions">
                        <a href="${paper.url}" target="_blank" class="btn btn-secondary btn-sm">查看原文</a>
                    </div>
                </div>
            </div>
        `;
        }).join('');
    }
    
    // 显示消息
    function showMessage(message, type) {
        const statusMessage = document.getElementById('statusMessage');
        statusMessage.textContent = message;
        statusMessage.className = 'status-message ' + type;
        statusMessage.style.display = 'block';
    }
});

