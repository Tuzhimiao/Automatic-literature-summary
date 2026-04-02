// 分析结果页面JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    // 从URL参数获取数据
    const params = new URLSearchParams(window.location.search);
    const topic = params.get('topic');
    
    // 显示主题
    document.getElementById('topicName').textContent = topic || '未知主题';
    
    // 从sessionStorage获取分析结果
    const resultData = sessionStorage.getItem('analysisResult');
    
    if (resultData) {
        const data = JSON.parse(resultData);
        displayResults(data);
    } else {
        // 如果没有数据，显示错误
        document.querySelector('.main-content').innerHTML = `
            <div class="card">
                <h2>❌ 错误</h2>
                <p>未找到分析结果，请返回重新分析。</p>
                <button class="btn btn-primary" onclick="window.location.href='/'">返回首页</button>
            </div>
        `;
    }
    
    // 显示结果
    function displayResults(data) {
        // 显示关键指标（只显示模型置信度）
        const metricsGrid = document.getElementById('metricsGrid');
        const modelConfidence = data.validation.model_confidence || data.validation.llm_confidence || 0.7;
        const confidenceLevel = getConfidenceLevel(modelConfidence);
        metricsGrid.innerHTML = `
            <div class="metric-card ${confidenceLevel.class}">
                <div class="label">模型置信度</div>
                <div class="value">${(modelConfidence * 100).toFixed(1)}%</div>
                <div class="confidence-badge">${confidenceLevel.text}</div>
            </div>
            <div class="metric-card">
                <div class="label">论文数量</div>
                <div class="value">${data.papers_count}</div>
            </div>
        `;
        
        // 如果有置信度理由，显示在下方（使用Markdown渲染）
        if (data.validation.confidence_reason) {
            const reasonDiv = document.createElement('div');
            reasonDiv.className = 'confidence-reason';
            // 使用marked库渲染Markdown
            const markdownContent = typeof marked !== 'undefined' ? marked.parse(data.validation.confidence_reason) : data.validation.confidence_reason;
            reasonDiv.innerHTML = `<strong>置信度说明：</strong><div class="markdown-content">${markdownContent}</div>`;
            metricsGrid.parentElement.appendChild(reasonDiv);
        }
        
        // 如果有冲突，显示警告（使用Markdown渲染）
        if (data.validation.conflicts && data.validation.conflicts.length > 0) {
            const conflictsDiv = document.createElement('div');
            conflictsDiv.className = 'conflicts-warning';
            // 对每个冲突项也使用Markdown渲染
            const conflictsHTML = data.validation.conflicts.map(c => {
                const conflictContent = typeof marked !== 'undefined' ? marked.parse(c) : c;
                return `<li><div class="markdown-content">${conflictContent}</div></li>`;
            }).join('');
            conflictsDiv.innerHTML = `<strong>⚠️ 检测到冲突：</strong><ul>${conflictsHTML}</ul>`;
            metricsGrid.parentElement.appendChild(conflictsDiv);
        }
        
        // 置信度等级判断函数
        function getConfidenceLevel(confidence) {
            if (confidence >= 0.8) return { text: '高', class: 'confidence-high' };
            if (confidence >= 0.6) return { text: '中', class: 'confidence-medium' };
            if (confidence >= 0.4) return { text: '低', class: 'confidence-low' };
            return { text: '很低', class: 'confidence-very-low' };
        }
        
        
        // 显示综述内容（新的5个部分结构）
        const summaryDiv = document.getElementById('summary');
        if (summaryDiv) {
            // 如果有新的5个部分结构，优先显示
            if (data.analysis.section1_research_intro) {
                let reviewHTML = '';
                
                if (data.analysis.section1_research_intro) {
                    reviewHTML += `<div class="review-section">
                        <h3>1. 研究介绍</h3>
                        <div class="markdown-content">${marked.parse(data.analysis.section1_research_intro)}</div>
                    </div>`;
                }
                
                if (data.analysis.section2_research_progress) {
                    reviewHTML += `<div class="review-section">
                        <h3>2. 研究进展</h3>
                        <div class="markdown-content">${marked.parse(data.analysis.section2_research_progress)}</div>
                    </div>`;
                }
                
                if (data.analysis.section3_research_status) {
                    reviewHTML += `<div class="review-section">
                        <h3>3. 研究现状</h3>
                        <div class="markdown-content">${marked.parse(data.analysis.section3_research_status)}</div>
                    </div>`;
                }
                
                if (data.analysis.section4_existing_methods) {
                    reviewHTML += `<div class="review-section">
                        <h3>4. 现有方法</h3>
                        <div class="markdown-content">${marked.parse(data.analysis.section4_existing_methods)}</div>
                    </div>`;
                }
                
                if (data.analysis.section5_future_development) {
                    reviewHTML += `<div class="review-section">
                        <h3>5. 未来发展</h3>
                        <div class="markdown-content">${marked.parse(data.analysis.section5_future_development)}</div>
                    </div>`;
                }
                
                summaryDiv.innerHTML = reviewHTML;
            } else {
                // 兼容旧格式 - 使用Markdown渲染
                if (data.analysis.summary) {
                    summaryDiv.innerHTML = `<div class="markdown-content">${marked.parse(data.analysis.summary)}</div>`;
                }
            }
        }
        
        // 显示关键发现（兼容旧格式，如果有新格式则隐藏）
        const keyFindings = document.getElementById('keyFindings');
        if (keyFindings) {
            if (data.analysis.section1_research_intro) {
                // 有新格式时隐藏关键发现和研究趋势部分
                const findingsSection = keyFindings.closest('.findings-section');
                if (findingsSection) findingsSection.style.display = 'none';
            } else if (data.analysis.key_findings && data.analysis.key_findings.length > 0) {
                keyFindings.innerHTML = data.analysis.key_findings.map(finding => 
                    `<li>${finding}</li>`
                ).join('');
            }
        }
        
        // 显示研究趋势（兼容旧格式，如果有新格式则隐藏）
        const researchTrends = document.getElementById('researchTrends');
        if (researchTrends) {
            if (data.analysis.section1_research_intro) {
                // 有新格式时隐藏研究趋势部分
                const trendsSection = researchTrends.closest('.trends-section');
                if (trendsSection) trendsSection.style.display = 'none';
            } else if (data.analysis.research_trends && data.analysis.research_trends.length > 0) {
                researchTrends.innerHTML = data.analysis.research_trends.map(trend => 
                    `<li>${trend}</li>`
                ).join('');
            }
        }
        
        // HTML转义函数
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // 显示推荐关键词
        const recommendedKeywordsSection = document.getElementById('recommendedKeywordsSection');
        const recommendedKeywords = document.getElementById('recommendedKeywords');
        if (data.recommended_keywords && data.recommended_keywords.length > 0) {
            recommendedKeywords.innerHTML = data.recommended_keywords.map(keyword => 
                `<span class="keyword-tag">${escapeHtml(keyword)}</span>`
            ).join('');
            recommendedKeywordsSection.style.display = 'block';
        } else {
            recommendedKeywordsSection.style.display = 'none';
        }
        
        // 显示论文数量
        const papersCount = document.getElementById('papersCount');
        if (papersCount && data.papers) {
            papersCount.textContent = `(${data.papers.length}篇)`;
        }
        
        // 显示论文列表（可滑动的悬浮窗）
        const papersList = document.getElementById('papersList');
        const paperDetails = data.paper_details || [];
        
        // 创建包装器以支持两列布局
        const papersListWrapper = document.createElement('div');
        papersListWrapper.className = 'papers-list';
        
        papersListWrapper.innerHTML = data.papers.map((paper, index) => {
            // 查找对应的论文详细信息
            const paperDetail = paperDetails.find(detail => detail.paper_id === paper.paper_id) || {};
            
            // 获取论文类型
            const paperType = paper.paper_type || paperDetail.paper_type || 'method';
            const paperTypeLabel = paperType === 'review' ? '📚 综述' : '🔬 方法论';
            const paperTypeClass = paperType === 'review' ? 'paper-type-review' : 'paper-type-method';
            
            // 获取推荐阅读程度（星级）
            const recScore = paperDetail.recommendation_score || paper.recommendation_score;
            let starDisplay = '';
            if (recScore !== null && recScore !== undefined) {
                const stars = '⭐'.repeat(recScore) + '☆'.repeat(5 - recScore);
                starDisplay = `<span class="recommendation-stars" title="推荐阅读程度：${recScore}星">${stars}</span>`;
            }
            
            // 根据论文类型构建问题列表
            let questions = [];
            if (paperType === 'review') {
                // 综述类论文：显示5个综述部分
                questions = [
                    { key: 'section1_research_intro', label: '1. 研究介绍' },
                    { key: 'section2_research_progress', label: '2. 研究进展' },
                    { key: 'section3_research_status', label: '3. 研究现状' },
                    { key: 'section4_existing_methods', label: '4. 现有方法' },
                    { key: 'section5_future_development', label: '5. 未来发展' }
                ];
            } else {
                // 方法论论文：显示8个问题
                questions = [
                    { key: 'q1_background', label: '1. 研究方向背景' },
                    { key: 'q2_implementation', label: '2. 实现内容' },
                    { key: 'q3_result', label: '3. 结果' },
                    { key: 'q4_modules', label: '4. 方法模块' },
                    { key: 'q5_related_work', label: '5. 相关工作' },
                    { key: 'q6_evaluation', label: '6. 评估' },
                    { key: 'q7_comparison', label: '7. 对比方法' },
                    { key: 'q8_summary', label: '8. 方法总结' }
                ];
            }
            
            // 构建悬浮窗内容
            let sidebarContent = '<div class="paper-detail-tooltip-content"><h5 style="margin-top: 0; color: var(--primary-color);">📋 详细分析</h5>';
            questions.forEach(q => {
                const answer = paperDetail[q.key] || '信息不足';
                sidebarContent += `<div class="tooltip-question"><strong>${q.label}:</strong><br>${escapeHtml(answer)}</div>`;
            });
            sidebarContent += '</div>';
            
            return `
            <div class="paper-item" style="position: relative;">
                <div class="paper-item-header">
                    <h4>${paper.title}</h4>
                </div>
                <div class="meta">
                    <span class="paper-type-badge ${paperTypeClass}">${paperTypeLabel}</span>
                    ${starDisplay}<br>
                    <strong>作者:</strong> ${paper.authors.join(', ')}<br>
                    <strong>来源:</strong> ${paper.source.toUpperCase()}<br>
                    ${paper.citation_count ? `<strong>引用:</strong> ${paper.citation_count} 次<br>` : ''}
                    <strong>链接:</strong> <a href="${paper.url}" target="_blank">查看论文</a>
                </div>
                <div class="paper-detail-sidebar">
                    ${sidebarContent}
                </div>
            </div>
        `;
        }).join('');
        
        // 将包装器插入到 papersList 中
        papersList.innerHTML = '';
        papersList.appendChild(papersListWrapper);
        
        // 显示可视化图表
        if (data.reports.timeline) {
            const timelineCard = document.getElementById('timelineCard');
            const timelineImage = document.getElementById('timelineImage');
            const timelineDownload = document.getElementById('timelineDownload');
            
            if (timelineCard && timelineImage) {
                timelineImage.src = data.reports.timeline;
                timelineImage.onerror = function() {
                    timelineCard.style.display = 'none';
                };
                timelineCard.style.display = 'block';
                
                if (timelineDownload) {
                    timelineDownload.href = data.reports.timeline;
                    timelineDownload.download = 'timeline.png';
                }
            }
        }
        
        // 显示词云图
        if (data.reports.wordcloud) {
            const wordcloudCard = document.getElementById('wordcloudCard');
            const wordcloudImage = document.getElementById('wordcloudImage');
            const wordcloudDownload = document.getElementById('wordcloudDownload');
            
            if (wordcloudCard && wordcloudImage) {
                wordcloudImage.src = data.reports.wordcloud;
                wordcloudImage.onerror = function() {
                    wordcloudCard.style.display = 'none';
                };
                wordcloudCard.style.display = 'block';
                
                if (wordcloudDownload) {
                    wordcloudDownload.href = data.reports.wordcloud;
                    wordcloudDownload.download = 'wordcloud.png';
                }
            }
        }
        
        // 显示关键词列表（如果有）
        if (data.analysis.keywords && data.analysis.keywords.length > 0) {
            // 可以在词云图下方显示关键词列表
            const wordcloudCard = document.getElementById('wordcloudCard');
            if (wordcloudCard) {
                const keywordsList = document.createElement('div');
                keywordsList.className = 'keywords-list';
                keywordsList.style.marginTop = '16px';
                keywordsList.style.paddingTop = '16px';
                keywordsList.style.borderTop = '1px solid var(--border-color)';
                keywordsList.innerHTML = `
                    <p style="margin-bottom: 8px; font-weight: 500;">关键词列表：</p>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        ${data.analysis.keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                    </div>
                `;
                const visualizationContent = wordcloudCard.querySelector('.visualization-content');
                if (visualizationContent) {
                    visualizationContent.appendChild(keywordsList);
                }
            }
        }
        
        
        // 显示下载按钮（报告文件）
        const downloadButtons = document.getElementById('downloadButtons');
        let buttonsHTML = `
            <a href="${data.reports.html}" target="_blank" class="download-btn">
                📄 HTML报告
            </a>
            <a href="${data.reports.markdown}" download class="download-btn">
                📝 Markdown报告
            </a>
        `;
        
        // 添加PDF下载按钮（如果有）
        if (data.reports.pdf) {
            buttonsHTML += `
                <a href="${data.reports.pdf}" target="_blank" class="download-btn">
                    📕 PDF报告
                </a>
            `;
        }
        
        // 添加BibTeX下载按钮（如果有）
        if (data.reports.bibtex) {
            buttonsHTML += `
                <a href="${data.reports.bibtex}" download class="download-btn">
                    📚 BibTeX文件
                </a>
            `;
        }
        
        downloadButtons.innerHTML = buttonsHTML;
        
        // 初始化问答功能
        initChat(data);
    }
    
    // 初始化问答功能
    function initChat(data) {
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        const enableWebSearch = document.getElementById('enableWebSearch');
        
        // 从URL或sessionStorage获取task_id
        const params = new URLSearchParams(window.location.search);
        let taskId = params.get('task_id');
        
        // 如果没有task_id，尝试从sessionStorage获取
        if (!taskId) {
            taskId = sessionStorage.getItem('currentTaskId');
        }
        
        // 如果还是没有，显示提示
        if (!taskId) {
            chatMessages.innerHTML = `
                <div class="chat-message assistant">
                    <div class="message-bubble">
                        <p>⚠️ 无法获取任务ID，问答功能可能无法正常工作。请从分析页面进入。</p>
                    </div>
                </div>
            `;
            chatInput.disabled = true;
            sendButton.disabled = true;
            return;
        }
        
        // 保存task_id到sessionStorage
        sessionStorage.setItem('currentTaskId', taskId);
        
        // 显示欢迎消息
        chatMessages.innerHTML = `
            <div class="chat-message assistant">
                <div class="message-bubble">
                    <p>👋 您好！我是您的研究助手。您可以基于已分析的论文向我提问。</p>
                    <p style="margin-top: 10px;">💡 提示：我已分析了 <strong>${data.papers_count || 0}</strong> 篇关于 <strong>${data.topic || '该主题'}</strong> 的论文。</p>
                    <p style="margin-top: 10px;">您可以询问：</p>
                    <ul style="margin-top: 5px; padding-left: 20px;">
                        <li>论文中的具体方法和技术细节</li>
                        <li>研究现状和发展趋势</li>
                        <li>不同方法的对比分析</li>
                        <li>最新的研究进展（如果启用联网搜索）</li>
                    </ul>
                </div>
            </div>
        `;
        
        // 发送消息函数
        async function sendMessage() {
            const question = chatInput.value.trim();
            if (!question) return;
            
            // 禁用输入
            chatInput.disabled = true;
            sendButton.disabled = true;
            
            // 显示用户消息
            const userMessage = document.createElement('div');
            userMessage.className = 'chat-message user';
            userMessage.innerHTML = `
                <div class="message-bubble">${question}</div>
            `;
            chatMessages.appendChild(userMessage);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // 清空输入框
            chatInput.value = '';
            
            // 显示加载状态
            const loadingMessage = document.createElement('div');
            loadingMessage.className = 'chat-message assistant';
            loadingMessage.innerHTML = `
                <div class="message-bubble">
                    <div class="chat-loading">正在思考</div>
                </div>
            `;
            chatMessages.appendChild(loadingMessage);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        task_id: taskId,
                        question: question,
                        enable_web_search: enableWebSearch.checked
                    })
                });
                
                const result = await response.json();
                
                // 移除加载消息
                loadingMessage.remove();
                
                if (!response.ok) {
                    throw new Error(result.error || '问答失败');
                }
                
                // 显示回答
                const answerMessage = document.createElement('div');
                answerMessage.className = 'chat-message assistant';
                
                // 解析回答中的来源标注
                let answerText = result.answer;
                const sourceMatches = answerText.match(/\[(论文来源|网络来源):[^\]]+\]/g);
                let sources = [];
                if (sourceMatches) {
                    sources = sourceMatches.map(m => m.replace(/[\[\]]/g, ''));
                    // 移除标注标记，保留文本
                    answerText = answerText.replace(/\[(论文来源|网络来源):[^\]]+\]/g, '');
                }
                
                let answerHTML = `<div class="message-bubble">${answerText.replace(/\n/g, '<br>')}</div>`;
                
                if (sources.length > 0) {
                    answerHTML += `<div class="message-source">📌 信息来源：${sources.join('; ')}</div>`;
                }
                
                answerMessage.innerHTML = answerHTML;
                chatMessages.appendChild(answerMessage);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                
            } catch (error) {
                console.error('Error:', error);
                
                // 移除加载消息
                loadingMessage.remove();
                
                // 显示错误消息
                const errorMessage = document.createElement('div');
                errorMessage.className = 'chat-message assistant';
                errorMessage.innerHTML = `
                    <div class="message-bubble" style="color: var(--danger-color);">
                        ❌ 抱歉，回答问题失败：${error.message}
                    </div>
                `;
                chatMessages.appendChild(errorMessage);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            } finally {
                // 恢复输入
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            }
        }
        
        // 绑定事件
        sendButton.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

