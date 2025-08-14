from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import json
import os
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
                    '中学3年': ['多項式', '平方根', '二次方程式', '二次関数', '相似', '円', '三平方の定理'],
                    '高校1年': ['数と式', '集合と論証', '二次関数', '図形と計量', 'データの分析'],
                    '高校2年': ['三角関数', '指数・対数関数', '微分', '積分', '数列'],
                    '高校3年': ['極限', '微分法の応用', '積分法の応用', '複素数平面', '確率分布']
                }
            },
            'english': {
                'units': {
                    '中学1年': ['be動詞', '一般動詞', '疑問文・否定文', '代名詞', '複数形'],
                    '中学2年': ['過去形', '未来形', '助動詞', '不定詞', '動名詞'],
                    '中学3年': ['現在完了形', '受動態', '関係代名詞', '間接疑問文'],
                    '高校1年': ['時制', '助動詞', '仮定法', '不定詞・動名詞', '分詞'],
                    '高校2年': ['関係詞', '比較', '仮定法', '語法'],
                    '高校3年': ['長文読解', '英作文', '語彙・イディオム', '文法総合']
                }
            }
        }

    def generate_problems(self, subject, grade, unit, problem_type, count, difficulty, options=None):
        """AIを使って問題を生成"""
        
        if subject == 'math':
            prompt = self._build_math_prompt(grade, unit, problem_type, count, difficulty, options)
        else:
            prompt = self._build_english_prompt(grade, unit, problem_type, count, difficulty, options)
        
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            problems_data = json.loads(response.text)
            return problems_data
        except Exception as e:
            print(f"AI生成エラー ({type(e).__name__}): {e}")
            return self._generate_fallback_problems(subject, grade, unit, count)

    def _build_math_prompt(self, grade, unit, problem_type, count, difficulty, options):
        """数学問題生成用プロンプト"""
        base_prompt = f"""
{grade}の数学「{unit}」に関する{problem_type}を{count}問作成してください。

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
"""
        
        if options and options.get('calculation_only'):
            base_prompt += "\n- 計算問題のみを出題する"
        if options and options.get('word_problems'):
            base_prompt += "\n- 文章問題も含める"
            
        return base_prompt

    def _build_english_prompt(self, grade, unit, problem_type, count, difficulty, options):
        """英語問題生成用プロンプト"""
        base_prompt = f"""
{grade}の英語「{unit}」に関する{problem_type}を{count}問作成してください。

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
- 問題は{grade}のレベルに適した語彙・文法を使用し、難易度は「{difficulty}」とすること
- 解説では文法ポイントも詳しく説明
- 実用的な例文を使用
- 解答解説は「ですます調」ではなく「である調」で書くこと
- "choices"は{problem_type}が「選択問題」の場合のみ含めること。それ以外の場合はnullではなくキー自体を省略すること。
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
        story.append(Paragraph("【問題】", self.title_style))
        
        for problem in problems_data.get('problems', []):
            question_text = f"問{problem['id']}. {problem['question']}"
            story.append(Paragraph(question_text, self.question_style))
            if 'choices' in problem and problem['choices']:
                for i, choice in enumerate(problem['choices']):
                    choice_text = f"({chr(65+i)}) {choice}"
                    story.append(Paragraph(choice_text, self.question_style))
            story.append(Spacer(1, 15))
        
        story.append(PageBreak())
        story.append(Paragraph("【解答・解説】", self.title_style))
        
        for problem in problems_data.get('problems', []):
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
            count=int(data.get('count', 5)),
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