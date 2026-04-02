// 历史记录详情页面JavaScript文件

// 全局变量存储recordId
let currentRecordId = null;

document.addEventListener('DOMContentLoaded', function() {
    // 从URL获取记录ID
    const pathParts = window.location.pathname.split('/');
    currentRecordId = pathParts[pathParts.length - 1];
    
    if (!currentRecordId || currentRecordId === 'history') {
        showError('未找到历史记录ID');
        return;
    }
    
    loadHistoryDetail(currentRecordId);
});

function loadHistoryDetail(recordId) {
    if (!recordId) {
        recordId = currentRecordId;
    }
    
    if (!recordId) {
        showError('未找到历史记录ID');
        return;
    }

function loadHistoryDetail(recordId) {
    const loadingState = document.getElementById('loadingState');
    const contentArea = document.getElementById('contentArea');
    const errorState = document.getElementById('errorState');
    
    // 显示加载状态
    loadingState.style.display = 'block';
    contentArea.style.display = 'none';
    errorState.style.display = 'none';
    
    fetch(`/api/history/${recordId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.history) {
                displayHistoryDetail(data.history);
                loadingState.style.display = 'none';
                contentArea.style.display = 'block';
            } else {
                showError(data.error || '历史记录不存在');
            }
        })
        .catch(error => {
            console.error('加载历史记录失败:', error);
            showError('加载历史记录失败: ' + error.message);
        });
}

function displayHistoryDetail(history) {
    // 显示主题
    document.getElementById('topicName').textContent = history.topic || '未知主题';
    
    // 显示关键指标
    displayMetrics(history.validation);
    
    // 显示综述报告
    displaySummary(history.analysis);
    
    // 显示关键发现和研究趋势
    displayFindingsAndTrends(history.analysis);
    
    // 显示子话题
    if (history.analysis.subtopics && history.analysis.subtopics.length > 0) {
        displaySubtopics(history.analysis.subtopics);
    }
    
    // 显示论文列表
    displayPapers(history.papers || []);
    
    // 显示报告下载链接
    displayReports(history.reports || {});
    
    // 显示时间轴（如果有）
    if (history.reports && history.reports.timeline) {
        displayTimeline(history.reports.timeline);
    }
    
    // 显示置信度诊断
    displayDiagnostic(history.validation);
}

function displayMetrics(validation) {
    const metricsGrid = document.getElementById('metricsGrid');
    const modelConfidence = validation.model_confidence || 0;
    
    metricsGrid.innerHTML = `
        <div class="metric-card">
            <div class="metric-label">模型置信度</div>
            <div class="metric-value">${(modelConfidence * 100).toFixed(1)}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">论文数量</div>
            <div class="metric-value">${validation.papers_count || 0}</div>
        </div>
    `;
}

function displaySummary(analysis) {
    const summaryDiv = document.getElementById('summary');
    
    // 如果有新的5部分结构，优先使用
    if (analysis.section1_research_intro) {
        let summaryHTML = '';
        
        if (analysis.section1_research_intro) {
            summaryHTML += `<div class="review-section">
                <h3>1. 研究介绍</h3>
                <div class="summary-content-text">${marked.parse(analysis.section1_research_intro)}</div>
            </div>`;
        }
        
        if (analysis.section2_research_progress) {
            summaryHTML += `<div class="review-section">
                <h3>2. 研究进展</h3>
                <div class="summary-content-text">${marked.parse(analysis.section2_research_progress)}</div>
            </div>`;
        }
        
        if (analysis.section3_research_status) {
            summaryHTML += `<div class="review-section">
                <h3>3. 研究现状</h3>
                <div class="summary-content-text">${marked.parse(analysis.section3_research_status)}</div>
            </div>`;
        }
        
        if (analysis.section4_existing_methods) {
            summaryHTML += `<div class="review-section">
                <h3>4. 现有方法</h3>
                <div class="summary-content-text">${marked.parse(analysis.section4_existing_methods)}</div>
            </div>`;
        }
        
        if (analysis.section5_future_development) {
            summaryHTML += `<div class="review-section">
                <h3>5. 未来发展</h3>
                <div class="summary-content-text">${marked.parse(analysis.section5_future_development)}</div>
            </div>`;
        }
        
        summaryDiv.innerHTML = summaryHTML;
    } else if (analysis.summary) {
        // 使用旧格式
        summaryDiv.innerHTML = `<div class="summary-content-text">${marked.parse(analysis.summary)}</div>`;
    } else {
        summaryDiv.innerHTML = '<p>暂无综述内容</p>';
    }
}

function displayFindingsAndTrends(analysis) {
    // 关键发现
    const keyFindings = document.getElementById('keyFindings');
    if (analysis.key_findings && analysis.key_findings.length > 0) {
        keyFindings.innerHTML = analysis.key_findings.map(finding => 
            `<li>${escapeHtml(finding)}</li>`
        ).join('');
    } else {
        keyFindings.innerHTML = '<li>暂无关键发现</li>';
    }
    
    // 研究趋势
    const researchTrends = document.getElementById('researchTrends');
    if (analysis.research_trends && analysis.research_trends.length > 0) {
        researchTrends.innerHTML = analysis.research_trends.map(trend => 
            `<li>${escapeHtml(trend)}</li>`
        ).join('');
    } else {
        researchTrends.innerHTML = '<li>暂无研究趋势</li>';
    }
}

function displaySubtopics(subtopics) {
    const subtopicsSection = document.getElementById('subtopicsSection');
    const subtopicsContent = document.getElementById('subtopicsContent');
    
    subtopicsSection.style.display = 'block';
    subtopicsContent.innerHTML = `
        <p style="margin-bottom: 15px; color: #666;">
            基于论文分析和综述内容，系统自动提取了以下出现频率高、具有代表性的关键词作为子话题。
        </p>
        <div style="display: flex; flex-wrap: wrap; gap: 10px;">
            ${subtopics.map((st, i) => `
                <span style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 0.95em;
                    font-weight: 500;
                ">${i + 1}. ${escapeHtml(st)}</span>
            `).join('')}
        </div>
    `;
}

function displayPapers(papers) {
    const papersList = document.getElementById('papersList');
    
    if (!papers || papers.length === 0) {
        papersList.innerHTML = '<p>暂无论文信息</p>';
        return;
    }
    
    papersList.innerHTML = papers.map((paper, index) => {
        const authors = paper.authors ? paper.authors.slice(0, 3).join(', ') : '未知';
        const authorsMore = paper.authors && paper.authors.length > 3 ? ` 等 ${paper.authors.length} 人` : '';
        const citationStr = paper.citation_count ? ` | 引用: ${paper.citation_count} 次` : '';
        const dateStr = paper.publication_date ? new Date(paper.publication_date).toLocaleDateString('zh-CN') : '未知';
        
        return `
            <div class="paper-item">
                <h4>${index + 1}. ${escapeHtml(paper.title)}</h4>
                <div class="paper-meta">
                    <strong>作者:</strong> ${escapeHtml(authors + authorsMore)}<br>
                    <strong>发表日期:</strong> ${dateStr}${citationStr}<br>
                    <strong>来源:</strong> ${escapeHtml(paper.source || '未知').toUpperCase()}<br>
                    ${paper.url ? `<strong>链接:</strong> <a href="${escapeHtml(paper.url)}" target="_blank">${escapeHtml(paper.url)}</a>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function displayReports(reports) {
    const downloadButtons = document.getElementById('downloadButtons');
    const buttons = [];
    
    if (reports.html) {
        buttons.push(`<a href="${reports.html}" target="_blank" class="btn btn-primary">📄 HTML报告</a>`);
    }
    if (reports.markdown) {
        buttons.push(`<a href="${reports.markdown}" target="_blank" class="btn btn-primary">📝 Markdown报告</a>`);
    }
    if (reports.pdf) {
        buttons.push(`<a href="${reports.pdf}" target="_blank" class="btn btn-primary">📕 PDF报告</a>`);
    }
    if (reports.bibtex) {
        buttons.push(`<a href="${reports.bibtex}" download class="btn btn-primary">📚 BibTeX文件</a>`);
    }
    if (reports.timeline) {
        buttons.push(`<a href="${reports.timeline}" download class="btn btn-secondary">📊 时间轴图表</a>`);
    }
    if (reports.topic_graph) {
        buttons.push(`<a href="${reports.topic_graph}" target="_blank" class="btn btn-secondary">🗺️ 主题图谱</a>`);
    }
    
    if (buttons.length > 0) {
        downloadButtons.innerHTML = buttons.join(' ');
    } else {
        downloadButtons.innerHTML = '<p>暂无报告文件</p>';
    }
}

function displayTimeline(timelinePath) {
    const timelineCard = document.getElementById('timelineCard');
    const timelineImage = document.getElementById('timelineImage');
    const timelineDownload = document.getElementById('timelineDownload');
    
    timelineCard.style.display = 'block';
    timelineImage.src = timelinePath;
    timelineDownload.href = timelinePath;
}

function displayDiagnostic(validation) {
    const diagnosticSection = document.getElementById('diagnosticSection');
    const diagnosticContent = document.getElementById('diagnosticContent');
    
    if (validation.confidence_reason || (validation.conflicts && validation.conflicts.length > 0)) {
        diagnosticSection.style.display = 'block';
        
        let html = '';
        
        if (validation.confidence_reason) {
            html += `
                <div class="diagnostic-item">
                    <h3>📊 置信度说明</h3>
                    <p>${escapeHtml(validation.confidence_reason)}</p>
                </div>
            `;
        }
        
        if (validation.conflicts && validation.conflicts.length > 0) {
            html += `
                <div class="diagnostic-item">
                    <h3>⚠️ 检测到的冲突</h3>
                    <ul>
                        ${validation.conflicts.map(conflict => `<li>${escapeHtml(conflict)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        diagnosticContent.innerHTML = html;
    }
}

function showError(message) {
    const loadingState = document.getElementById('loadingState');
    const contentArea = document.getElementById('contentArea');
    const errorState = document.getElementById('errorState');
    const errorMessage = document.getElementById('errorMessage');
    
    loadingState.style.display = 'none';
    contentArea.style.display = 'none';
    errorState.style.display = 'block';
    errorMessage.textContent = message;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

