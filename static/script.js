// アプリケーション状態管理
class AppState {
    constructor() {
        this.currentProblems = null;
        this.currentSettings = null;
        this.isLoading = false;
    }
    
    setProblems(problems) {
        this.currentProblems = problems;
    }
    
    setSettings(settings) {
        this.currentSettings = settings;
    }
    
    setLoading(status) {
        this.isLoading = status;
    }
}

// グローバル状態
const appState = new AppState();

// DOM要素の取得
const elements = {
    form: document.getElementById('problemForm'),
    subjectSelect: document.getElementById('subject'),
    gradeSelect: document.getElementById('grade'),
    unitSelect: document.getElementById('unit'),
    vocabularyGroup: document.getElementById('vocabularyGroup'),
    generateBtn: document.getElementById('generateBtn'),
    loadingSection: document.getElementById('loadingSection'),
    previewSection: document.getElementById('previewSection'),
    problemsPreview: document.getElementById('problemsPreview'),
    editBtn: document.getElementById('editBtn'),
    regenerateBtn: document.getElementById('regenerateBtn'),
    downloadBtn: document.getElementById('downloadBtn'),
    editModal: document.getElementById('editModal'),
    editableProblems: document.getElementById('editableProblems'),
    closeModal: document.getElementById('closeModal'),
    saveEditsBtn: document.getElementById('saveEditsBtn'),
    cancelEditsBtn: document.getElementById('cancelEditsBtn')
};

// 学年オプション
const gradeOptions = {
    math: ['中学1年', '中学2年', '中学3年', '高校1年', '高校2年', '高校3年'],
    english: ['中学1年', '中学2年', '中学3年', '高校1年', '高校2年', '高校3年']
};

// 初期化
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    updateVocabularyVisibility();
});

// イベントリスナーの設定
function initializeEventListeners() {
    // 科目変更時の処理
    elements.subjectSelect.addEventListener('change', handleSubjectChange);
    
    // 学年変更時の処理
    elements.gradeSelect.addEventListener('change', handleGradeChange);
    
    // フォーム送信の処理
    elements.form.addEventListener('submit', handleFormSubmit);
    
    // ボタンクリックの処理
    elements.editBtn.addEventListener('click', openEditModal);
    elements.regenerateBtn.addEventListener('click', handleRegenerate);
    elements.downloadBtn.addEventListener('click', handleDownload);
    
    // モーダル関連の処理
    elements.closeModal.addEventListener('click', closeEditModal);
    elements.cancelEditsBtn.addEventListener('click', closeEditModal);
    elements.saveEditsBtn.addEventListener('click', saveEdits);
    
    // モーダル背景クリックで閉じる
    elements.editModal.addEventListener('click', function(e) {
        if (e.target === elements.editModal) {
            closeEditModal();
        }
    });
}

// 科目変更処理
function handleSubjectChange() {
    const subject = elements.subjectSelect.value;
    updateGradeOptions(subject);
    updateVocabularyVisibility();
    resetUnitSelect();
}

// 学年オプション更新
function updateGradeOptions(subject) {
    elements.gradeSelect.innerHTML = '<option value="">選択してください</option>';
    
    if (subject && gradeOptions[subject]) {
        gradeOptions[subject].forEach(grade => {
            const option = document.createElement('option');
            option.value = grade;
            option.textContent = grade;
            elements.gradeSelect.appendChild(option);
        });
    }
}

// 単語リスト表示/非表示
function updateVocabularyVisibility() {
    const isEnglish = elements.subjectSelect.value === 'english';
    elements.vocabularyGroup.style.display = isEnglish ? 'block' : 'none';
}

// 学年変更処理
async function handleGradeChange() {
    const subject = elements.subjectSelect.value;
    const grade = elements.gradeSelect.value;
    
    if (subject && grade) {
        await updateUnitOptions(subject, grade);
    } else {
        resetUnitSelect();
    }
}

// 単元オプション更新
async function updateUnitOptions(subject, grade) {
    try {
        elements.unitSelect.innerHTML = '<option value="">読み込み中...</option>';
        
        const response = await fetch(`/api/get_units?subject=${subject}&grade=${encodeURIComponent(grade)}`);
        const data = await response.json();
        
        if (response.ok) {
            elements.unitSelect.innerHTML = '<option value="">選択してください</option>';
            data.units.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit;
                option.textContent = unit;
                elements.unitSelect.appendChild(option);
            });
        } else {
            throw new Error(data.error || '単元の取得に失敗しました');
        }
    } catch (error) {
        console.error('単元取得エラー:', error);
        elements.unitSelect.innerHTML = '<option value="">エラーが発生しました</option>';
        showError('単元の取得に失敗しました。');
    }
}

// 単元選択をリセット
function resetUnitSelect() {
    elements.unitSelect.innerHTML = '<option value="">学年を先に選択してください</option>';
}

// フォーム送信処理
async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (appState.isLoading) return;
    
    const formData = collectFormData();
    if (!validateFormData(formData)) return;
    
    appState.setSettings(formData);
    await generateProblems(formData);
}

// フォームデータ収集
function collectFormData() {
    const formData = new FormData(elements.form);
    const data = {
        subject: formData.get('subject'),
        grade: formData.get('grade'),
        unit: formData.get('unit'),
        problemType: formData.get('problemType'),
        count: formData.get('count'),
        difficulty: formData.get('difficulty'),
        options: {}
    };
    
    // チェックボックスオプション
    if (formData.get('calculationOnly')) {
        data.options.calculation_only = true;
    }
    if (formData.get('wordProblems')) {
        data.options.word_problems = true;
    }
    
    // 英語の単語リスト
    const vocabularyList = formData.get('vocabularyList');
    if (vocabularyList && vocabularyList.trim()) {
        data.options.vocabulary_list = vocabularyList.trim();
    }
    
    return data;
}

// フォームデータ検証
function validateFormData(data) {
    const required = ['subject', 'grade', 'unit', 'problemType'];
    
    for (const field of required) {
        if (!data[field]) {
            showError(`${getFieldDisplayName(field)}を選択してください。`);
            return false;
        }
    }
    
    const count = parseInt(data.count);
    if (count < 1 || count > 50) {
        showError('問題数は1〜50問の範囲で指定してください。');
        return false;
    }
    
    return true;
}

// フィールド表示名取得
function getFieldDisplayName(field) {
    const names = {
        subject: '科目',
        grade: '学年',
        unit: '単元',
        problemType: '問題形式'
    };
    return names[field] || field;
}

// 問題生成
async function generateProblems(data) {
    try {
        showLoading(true);
        hidePreview();
        
        const response = await fetch('/api/generate_problems', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            appState.setProblems(result);
            displayProblems(result);
            showPreview();
        } else {
            throw new Error(result.error || '問題生成に失敗しました');
        }
    } catch (error) {
        console.error('問題生成エラー:', error);
        showError('問題の生成に失敗しました: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// ローディング表示制御
function showLoading(show) {
    appState.setLoading(show);
    elements.loadingSection.style.display = show ? 'block' : 'none';
    elements.generateBtn.disabled = show;
    elements.generateBtn.textContent = show ? '生成中...' : '✨ 問題を生成する';
}

// プレビュー表示制御
function showPreview() {
    elements.previewSection.style.display = 'block';
    elements.previewSection.scrollIntoView({ behavior: 'smooth' });
}

function hidePreview() {
    elements.previewSection.style.display = 'none';
}

// 問題表示
function displayProblems(problemsData) {
    const problems = problemsData.problems || [];
    let html = '';
    
    problems.forEach((problem, index) => {
        html += `
            <div class="problem-item" data-problem-id="${problem.id}">
                <div class="problem-question">
                    <strong>問${problem.id}.</strong> ${escapeHtml(problem.question)}
                </div>
                
                ${problem.choices ? `
                    <div class="problem-choices">
                        ${problem.choices.map((choice, i) => 
                            `<div class="problem-choice">(${String.fromCharCode(65 + i)}) ${escapeHtml(choice)}</div>`
                        ).join('')}
                    </div>
                ` : ''}
                
                <div class="problem-answer">
                    <strong>解答:</strong> ${escapeHtml(problem.answer)}
                </div>
                
                ${problem.explanation ? `
                    <div class="problem-explanation">
                        <strong>解説:</strong> ${escapeHtml(problem.explanation)}
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    if (html === '') {
        html = '<p>問題が生成されませんでした。設定を確認して再試行してください。</p>';
    }
    
    elements.problemsPreview.innerHTML = html;
}

// HTML エスケープ
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 再生成処理
async function handleRegenerate() {
    if (appState.currentSettings) {
        await generateProblems(appState.currentSettings);
    }
}

// PDF ダウンロード処理
async function handleDownload() {
    if (!appState.currentProblems || !appState.currentSettings) {
        showError('ダウンロードできる問題がありません。');
        return;
    }
    
    try {
        elements.downloadBtn.disabled = true;
        elements.downloadBtn.textContent = 'ダウンロード中...';
        
        const response = await fetch('/api/generate_pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                problems: appState.currentProblems,
                ...appState.currentSettings
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `問題プリント_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } else {
            const error = await response.json();
            throw new Error(error.error || 'PDFの生成に失敗しました');
        }
    } catch (error) {
        console.error('PDF生成エラー:', error);
        showError('PDFの生成に失敗しました: ' + error.message);
    } finally {
        elements.downloadBtn.disabled = false;
        elements.downloadBtn.textContent = '📥 PDFダウンロード';
    }
}

// 編集モーダルを開く
function openEditModal() {
    if (!appState.currentProblems) return;
    
    createEditForm();
    elements.editModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// 編集フォーム作成
function createEditForm() {
    const problems = appState.currentProblems.problems || [];
    let html = '';
    
    problems.forEach(problem => {
        html += `
            <div class="editable-problem" data-problem-id="${problem.id}">
                <h4>問${problem.id}</h4>
                
                <div class="form-group">
                    <label>問題文</label>
                    <textarea name="question" rows="3">${escapeHtml(problem.question)}</textarea>
                </div>
                
                ${problem.choices ? `
                    <div class="form-group">
                        <label>選択肢（1行に1つずつ）</label>
                        <textarea name="choices" rows="4">${problem.choices.map(c => escapeHtml(c)).join('\n')}</textarea>
                    </div>
                ` : ''}
                
                <div class="form-group">
                    <label>解答</label>
                    <input type="text" name="answer" value="${escapeHtml(problem.answer)}">
                </div>
                
                <div class="form-group">
                    <label>解説</label>
                    <textarea name="explanation" rows="3">${escapeHtml(problem.explanation || '')}</textarea>
                </div>
            </div>
        `;
    });
    
    elements.editableProblems.innerHTML = html;
}

// 編集を保存
function saveEdits() {
    const editableProblems = elements.editableProblems.querySelectorAll('.editable-problem');
    const updatedProblems = [];
    
    editableProblems.forEach(problemElement => {
        const problemId = problemElement.dataset.problemId;
        const question = problemElement.querySelector('textarea[name="question"]').value.trim();
        const answer = problemElement.querySelector('input[name="answer"]').value.trim();
        const explanation = problemElement.querySelector('textarea[name="explanation"]').value.trim();
        
        const problem = {
            id: parseInt(problemId),
            question: question,
            answer: answer,
            explanation: explanation
        };
        
        // 選択肢がある場合
        const choicesTextarea = problemElement.querySelector('textarea[name="choices"]');
        if (choicesTextarea) {
            const choicesText = choicesTextarea.value.trim();
            if (choicesText) {
                problem.choices = choicesText.split('\n').map(c => c.trim()).filter(c => c);
            }
        }
        
        updatedProblems.push(problem);
    });
    
    // 状態を更新
    appState.currentProblems.problems = updatedProblems;
    
    // プレビューを更新
    displayProblems(appState.currentProblems);
    
    // モーダルを閉じる
    closeEditModal();
    
    showSuccess('問題を更新しました。');
}

// 編集モーダルを閉じる
function closeEditModal() {
    elements.editModal.style.display = 'none';
    document.body.style.overflow = 'auto';
}

// エラーメッセージ表示
function showError(message) {
    alert('エラー: ' + message);
}

// 成功メッセージ表示
function showSuccess(message) {
    // 簡易的な成功メッセージ表示
    const successDiv = document.createElement('div');
    successDiv.textContent = message;
    successDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #48bb78;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(72, 187, 120, 0.3);
        z-index: 1001;
        font-weight: 500;
    `;
    
    document.body.appendChild(successDiv);
    
    setTimeout(() => {
        document.body.removeChild(successDiv);
    }, 3000);
}