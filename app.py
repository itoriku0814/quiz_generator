from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import json
import os
import re 
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import tempfile
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# Gemini API設定
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    raise ValueError("エラー: 環境変数に GEMINI_API_KEY が設定されていません。")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# 日本語フォントの設定
try:
    pdfmetrics.registerFont(TTFont('NotoSansCJK', 'NotoSansJP-Regular.ttf'))
    FONT_NAME = 'NotoSansCJK'
except Exception as e:
    print(f"フォント読み込みエラー: {e}")
    print("日本語フォントが読み込めないため、英語フォント(Helvetica)にフォールバックします。文字化けする可能性があります。")
    FONT_NAME = 'Helvetica'

class ProblemGenerator:
    def __init__(self):
        self.subject_templates = {
            'math': {
                'units': {
                    '中学1年': ['正負の数', '文字と式', '一次方程式', '比例・反比例', '平面図形', '空間図形', 'データの活用'],
                    '中学2年': ['式の計算', '連立方程式', '一次関数', '図形の性質', '確率'],
                    '中学3年': ['展開と因数分解', '平方根', '二次方程式', '二次関数', '相似', '円', '三平方の定理', '標本調査'],
                    '数学ⅠA': ['数と式', '集合と論証', '二次関数', '図形と計量', 'データの分析', '場合の数と確率', '整数の性質', '平面図形と空間図形'],
                    '数学ⅡB': ['式と証明', '複素数と方程式', '図形と方程式', '三角関数', '指数・対数関数', '微分法', '積分法', '数列', '確率分布'],
                    '数学ⅢC': ['分数関数と無理関数', '極限', '微分法', '微分法の応用', '積分法', '積分法の応用', 'ベクトル', '複素数平面', '二次曲線']
                }
            },
            'english': {
                'units': {
                    '中学1年': ['be動詞', '一般動詞', '疑問文・否定文', '代名詞', '複数形'],
                    '中学2年': ['過去形', '未来形', '助動詞', '不定詞', '動名詞'],
                    '中学3年': ['現在完了形', '受動態', '関係代名詞', '間接疑問文'],
                    '高校英文法': [
                        '時制', 
                        '助動詞', 
                        '受動態', 
                        '不定詞', 
                        '動名詞', 
                        '分詞', 
                        '関係詞', 
                        '比較', 
                        '仮定法', 
                        '接続詞',
                        '強調・倒置・挿入・省略', 
                        '一致・話法', 
                        '否定構文',
                        '名詞構文' ,
                        '文法総合'
                        ],
                    '高校英語長文': ['文化', '日常生活', '自然', '科学・技術', '社会', '産業', '歴史', '環境', '教育', '健康', '国際問題']
                }
            }
        }

    def _fix_json_escapes(self, json_string: str) -> str:
        """
        AIが生成したJSON文字列内の、あらゆる不正なバックスラッシュを修正する。
        """
        valid_escapes = {
            '\\n': '__NEWLINE__',
            '\\"': '__QUOTE__',
            '\\\\': '__BACKSLASH__',
            '\\/': '__SLASH__',
            '\\b': '__BACKSPACE__',
            '\\f': '__FORMFEED__',
            '\\r': '__CARRIAGERETURN__',
            '\\t': '__TAB__',
        }
        for original, placeholder in valid_escapes.items():
            json_string = json_string.replace(original, placeholder)
        
        json_string = json_string.replace('\\', '\\\\')
        
        for original, placeholder in valid_escapes.items():
            json_string = json_string.replace(placeholder, original)
            
        return json_string


    def generate_problems(self, subject, grade, unit, problem_type, count, difficulty, options=None):
        """AIを使って問題を生成"""
        
        if grade == '高校英語長文':
            # 「高校英語長文」用のプロンプト関数を呼び出すように修正
            prompt = self._build_english_reading_prompt(grade, unit, problem_type, count, difficulty)
        elif subject == 'math':
            prompt = self._build_math_prompt(grade, unit, problem_type, count, difficulty, options)
        else:
            # 「高校英文法」など、上記以外の英語の問題
            prompt = self._build_english_prompt(grade, unit, problem_type, count, difficulty, options)
        
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            raw_text = response.text
            fixed_text = self._fix_json_escapes(raw_text)
            problems_data = json.loads(fixed_text)
            
            return problems_data
        except Exception as e:
            print(f"AI生成エラー ({type(e).__name__}): {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                print("--- 問題が発生したテキスト ---")
                print(response.text)
                print("--------------------------")
            return self._generate_fallback_problems(subject, grade, unit, count)

    # ▼▼▼ 長文読解用プロンプト生成関数 ▼▼▼
    # ▼▼▼ 関数の引数に problem_type を追加 ▼▼▼
    def _build_english_reading_prompt(self, grade, unit, problem_type, count, difficulty, paragraph_count=None):
        """高校英語長文問題生成用プロンプト"""

        # ▼▼▼ 指示文を動的に生成するロジックを追加 ▼▼▼
        if problem_type == "おまかせ (ミックス)":
            task_instruction = f"そして、その長文の内容に関する問題を、選択問題、穴埋め問題、記述問題をバランス良く組み合わせて合計{count}問作成してください。"
        else:
            task_instruction = f"そして、その長文の内容に関する{problem_type}を{count}問作成してください。"

        return f"""
高校生レベルの英語長文を1つ、{paragraph_count}段落構成で生成してください。長文のトピックは「{unit}」に関連するものとします。
{task_instruction}

難易度は「{difficulty}」でお願いします。

以下の形式でJSONで回答してください：
{{
  "reading_passage": "生成した英語長文",
  "questions": [
    {{
      "id": 1,
      "question": "設問文",
      "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
      "answer": "正解",
      "explanation": "詳しい解説"
    }}
  ]
}}

要件：
- 長文は{grade}のレベルに適した語彙・文法を使用すること。
- 記述問題の場合、簡潔に答えられる問題にすること。
- 1個の問題の中に2つ以上の要素を含めないこと。
- 段落ごとの文章量は、平均して100-150語程度とすること。
- 全て同じようなジャンルの問題にはしないこと。
- `questions`配列には、必ず{count}個の問題オブジェクトを含めること。
- 設問は長文の内容に関するものにすること。
- "choices"は選択問題の場合のみ含めること。
- 解説は「である調」で、簡潔に記述すること。
- 数式はLaTeX記法 (例: \\( ... \\) や $...$) を一切使わず、プレーンテキストと一般的な記号(+, -, *, /, ^)のみで表現すること。
"""

    def _build_math_prompt(self, grade, unit, problem_type, count, difficulty, options):
        """数学問題生成用プロンプト"""

        if problem_type == "おまかせ (ミックス)":
            instruction = f"{grade}の数学「{unit}」に関する問題を、選択問題、穴埋め問題、記述問題をバランス良く組み合わせて合計{count}問作成してください。"
        else:
            instruction = f"{grade}の数学「{unit}」に関する{problem_type}を{count}問作成してください。"

        base_prompt = f"""
    {instruction}

以下の形式でJSONで回答してください：
{{
    "problems": [
        {{
            "id": 1,
            "question": "問題文",
            "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
            "answer": "正解",
            "explanation": "詳しい解説"
        }}
    ]
}}

要件：
- 問題は{grade}のレベルに適した、難易度「{difficulty}」で作成すること
- 解説は生徒が理解しやすいよう詳しく書く
- 計算過程も含める
- "choices"は{problem_type}が「選択問題」の場合のみ含めること。それ以外の場合はnullではなくキー自体を省略すること。
- 【最重要ルール】JSONの仕様を厳格に遵守してください。JSON文字列内でバックスラッシュ(`\\`)を1つだけ使用することは絶対に許されません。
- LaTeX記法などでバックスラッシュを使う場合は、必ずそれ自体をエスケープした二重バックスラッシュ(`\\\\`)を使用してください。
- 正しい例: `{{"formula": "\\\\sqrt{{2}}"}}`
- 間違った例: `{{"formula": "\\sqrt{{2}}"}}` (この形式だとJSONエラーになります)
- 解答解説は「ですます調」ではなく、簡潔な「である調」で記述すること。
- 解説は、要点を押さえて、可能な限り簡潔に記述すること。計算過程は主要なステップのみを示すこと。
- pi, theta, sigma, alpha, betaなどの英語はそれぞれの記号（π, θ, Σ, α, β）を使用すること。
- _barはバー（上線）を意味するので、例えば「x_bar」は「x_」と表記すること。
- sqrtは平方根を意味するので、例えば「sqrt(2)」は「√2」と表記すること。
- べき乗は「^」は使用せず、例えば「x^2」は「x²」と表記すること。
- 数式はLaTeX記法 (例: \\( ... \\) や $...$) を一切使わず、プレーンテキストと一般的な記号(+, -, *, /, ^)のみで表現すること。
- 「*」は使わないこと
"""
        
        if grade == "数学ⅡB" and unit in ["微分法", "積分法"]:
            base_prompt += "\n- 重要：必ず数学Ⅱの範囲（多項式関数の微分・積分）のみで問題を作成してください。数学Ⅲで扱う関数（三角関数、指数関数、対数関数など）の微分・積分は絶対に含めないでください。"

        if options and options.get('calculation_only'):
            base_prompt += "\n- 計算問題のみを出題する"
        if options and options.get('word_problems'):
            base_prompt += "\n- 文章問題も含める"
            
        return base_prompt

    def _build_english_prompt(self, grade, unit, problem_type, count, difficulty, options):
        """英文法問題生成用プロンプト"""

        # ▼▼▼ 指示文を動的に生成するロジックを追加 ▼▼▼
        if problem_type == "おまかせ (ミックス)":
            task_instruction = f"{grade}の英語「{unit}」に関する問題を、選択問題、穴埋め問題、記述問題をバランス良く組み合わせて合計{count}問作成してください。"
        else:
            task_instruction = f"{grade}の英語「{unit}」に関する{problem_type}を{count}問作成してください。"

        base_prompt = f"""
{task_instruction}

以下の形式でJSONで回答してください：
{{
    "problems": [
        {{
            "id": 1,
            "question": "問題文",
            "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
            "answer": "正解",
            "explanation": "詳しい解説（文法ポイントも含む）"
        }}
    ]
}}

要件：
- 難易度は「{difficulty}」とすること
- 解説では文法ポイントも詳しく説明
- 実用的な例文を使用
- 全て同じようなジャンルの問題にはしないこと。
- 問題文は日本語にすること。
- "choices"は{problem_type}が「選択問題」の場合のみ含めること。それ以外の場合はnullではなくキー自体を省略すること。
- JSON文字列内にバックスラッシュ(`\\`)を含める場合は、必ず二重バックスラッシュ(`\\\\`)としてエスケープすること。
- 解答解説は「ですます調」ではなく、簡潔な「である調」で記述すること。
- 数式はLaTeX記法 (例: \\( ... \\) や $...$) を一切使わず、プレーンテキストと一般的な記号(+, -, *, /, ^)のみで表現すること。
- 「*」は使わないこと
"""
        
        if options and options.get('vocabulary_list'):
            base_prompt += f"\n- 以下の単語を含める: {options['vocabulary_list']}"
            
        return base_prompt

    def _generate_fallback_problems(self, subject, grade, unit, count):
        """AIが使えない場合の代替問題生成"""
        problems = []
        for i in range(min(count, 3)):
            if subject == 'math':
                problems.append({
                    "id": i + 1,
                    "question": f"AIとの通信に失敗しました。{unit}に関する基本問題{i + 1}",
                    "answer": "解答例",
                    "explanation": "解説例"
                })
            else:
                problems.append({
                    "id": i + 1,
                    "question": f"AIとの通信に失敗しました。Choose the correct answer for {unit} (Question {i + 1})",
                    "choices": ["Option A", "Option B", "Option C", "Option D"],
                    "answer": "Option A",
                    "explanation": "解説例"
                })
        
        return {"problems": problems}

    def get_units_for_grade(self, subject, grade):
        """学年に応じた単元リストを取得"""
        return self.subject_templates.get(subject, {}).get('units', {}).get(grade, [])

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_styles()

    def setup_styles(self):
        self.title_style = ParagraphStyle(
            'CustomTitle', parent=self.styles['Heading1'], fontName=FONT_NAME,
            fontSize=16, spaceAfter=20, alignment=1
        )
        self.question_style = ParagraphStyle(
            'Question', parent=self.styles['Normal'], fontName=FONT_NAME,
            fontSize=12, spaceAfter=10, leftIndent=10
        )
        self.answer_style = ParagraphStyle(
            'Answer', parent=self.styles['Normal'], fontName=FONT_NAME,
            fontSize=11, spaceAfter=15, leftIndent=20, textColor=colors.blue
        )
        # ▼▼▼ 長文用のスタイルを追加 ▼▼▼
        self.passage_style = ParagraphStyle(
            'Passage', parent=self.styles['Normal'], fontName=FONT_NAME,
            fontSize=12, spaceAfter=15, leftIndent=10, leading=16
        )

    def generate_pdf(self, problems_data, subject, grade, unit):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_filename = temp_file.name
        temp_file.close()
        
        doc = SimpleDocTemplate(temp_filename, pagesize=A4,
                              rightMargin=20*mm, leftMargin=20*mm,
                              topMargin=20*mm, bottomMargin=20*mm)
        story = []
        title = f"{subject.upper()} - {grade} - {unit}"
        story.append(Paragraph(title, self.title_style))
        story.append(Spacer(1, 20))
        
        # ▼▼▼ PDF生成ロジックを修正 ▼▼▼
        # 長文形式の場合
        if 'reading_passage' in problems_data:
            story.append(Paragraph("【長文】", self.title_style))
            passage_text = problems_data['reading_passage'].replace('\n', '<br/>')
            story.append(Paragraph(passage_text, self.passage_style))
            story.append(Spacer(1, 15))
            
            story.append(Paragraph("【問題】", self.title_style))
            question_list = problems_data.get('questions', [])
            
            for problem in question_list:
                question_text = f"問{problem['id']}. {problem['question']}"
                story.append(Paragraph(question_text, self.question_style))
                if 'choices' in problem and problem['choices']:
                    for i, choice in enumerate(problem['choices']):
                        choice_text = f"({chr(65+i)}) {choice}"
                        story.append(Paragraph(choice_text, self.question_style))
                story.append(Spacer(1, 15))
            
            story.append(PageBreak())
            story.append(Paragraph("【解答・解説】", self.title_style))
            
            for problem in question_list:
                answer_text = f"問{problem['id']}. 解答: {problem['answer']}"
                story.append(Paragraph(answer_text, self.answer_style))
                explanation_text = f"解説: {problem.get('explanation', '解説はありません。')}"
                story.append(Paragraph(explanation_text, self.question_style))
                story.append(Spacer(1, 20))
        
        # 通常形式の場合
        else:
            story.append(Paragraph("【問題】", self.title_style))
            problem_list = problems_data.get('problems', [])

            for problem in problem_list:
                question_text = f"問{problem['id']}. {problem['question']}"
                story.append(Paragraph(question_text, self.question_style))
                if 'choices' in problem and problem['choices']:
                    for i, choice in enumerate(problem['choices']):
                        choice_text = f"({chr(65+i)}) {choice}"
                        story.append(Paragraph(choice_text, self.question_style))
                story.append(Spacer(1, 15))
            
            story.append(PageBreak())
            story.append(Paragraph("【解答・解説】", self.title_style))
            
            for problem in problem_list:
                answer_text = f"問{problem['id']}. 解答: {problem['answer']}"
                story.append(Paragraph(answer_text, self.answer_style))
                explanation_text = f"解説: {problem.get('explanation', '解説はありません。')}"
                story.append(Paragraph(explanation_text, self.question_style))
                story.append(Spacer(1, 20))
        
        doc.build(story)
        return temp_filename

problem_generator = ProblemGenerator()
pdf_generator = PDFGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_units')
def get_units():
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    if not subject or not grade:
        return jsonify({'error': 'Subject and grade are required'}), 400
    units = problem_generator.get_units_for_grade(subject, grade)
    return jsonify({'units': units})

@app.route('/api/generate_problems', methods=['POST'])
def generate_problems():
    data = request.get_json()
    try:
        problems = problem_generator.generate_problems(
            subject=data.get('subject'),
            grade=data.get('grade'),
            unit=data.get('unit'),
            problem_type=data.get('problemType'),
            count=int(data.get('count', 3)),
            difficulty=data.get('difficulty', '標準'),
            options=data.get('options')
        )
        return jsonify(problems)
    except Exception as e:
        print(f"APIルートエラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_pdf', methods=['POST'])
def generate_pdf():
    data = request.get_json()
    try:
        pdf_path = pdf_generator.generate_pdf(
            problems_data=data.get('problems'),
            subject=data.get('subject'),
            grade=data.get('grade'),
            unit=data.get('unit')
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{data.get('subject')}_{data.get('grade')}_{data.get('unit')}_{timestamp}.pdf"
        return send_file(pdf_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        print(f"PDF生成ルートエラー: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)