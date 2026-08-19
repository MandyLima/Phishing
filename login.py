import sqlite3
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from html import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
PORT = 5000

SESSOES = {}


# ---------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            senha TEXT NOT NULL,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# Leitura de Arquivos Estáticos e Páginas Dinâmicas
# ---------------------------------------------------------------------

def ler_arquivo(nome_arquivo):
    caminho = os.path.join(BASE_DIR, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read()
    return None


def pagina_resultado(email):
    email_seguro = escape(email)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resultado - Simulação Acadêmica</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #fef9f0, #f4f7ff);
        min-height:100vh; color:#22243a; padding:30px 20px;
        display: flex; align-items: center; justify-content: center;
    }}
    .container {{ width:100%; max-width:600px; margin:0 auto; }}
    .header {{ text-align:center; margin-bottom:25px; }}
    .logo {{
        width:70px; height:70px; margin:0 auto 20px; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        background:#e2711d; color:white; font-size:32px; font-weight:bold;
    }}
    .header h1 {{ font-size:28px; margin-bottom:10px; color:#1c1e33; }}
    .header p {{ color:#5b5e78; line-height:1.6; }}
    .card {{
        background:white; border-radius:16px; padding:28px; margin-bottom:20px;
        box-shadow:0 10px 30px rgba(30,20,60,.08); border:1px solid #eae7f5;
    }}
    .danger {{
        background:#fff4ec; border:1px solid #f7cfa8; border-left:5px solid #e2711d;
        border-radius:10px; padding:18px; color:#7a3d0e; line-height:1.6; margin-bottom:22px;
    }}
    .danger strong {{ color:#a1490f; }}
    .success {{
        background:#eefaf1; border:1px solid #b7e6c4; border-radius:10px; padding:16px;
        color:#1f6b3a; line-height:1.6; margin-bottom:22px;
    }}
    .email-box {{
        background:#f7f7fb; border:1px solid #e5e3f0; border-radius:10px; padding:14px;
        margin-top:10px; word-break:break-word; color:#3c3d55; font-weight: bold;
    }}
    h2 {{ font-size:19px; margin-bottom:14px; color:#1c1e33; }}
    .button {{
        display:inline-block; text-decoration:none; background:#6446d0; color:white;
        padding:12px 20px; border-radius:9px; font-weight:bold; margin-top:15px;
    }}
    .button:hover {{ background:#5638b3; }}
    .center {{ text-align:center; }}
    @media (max-width:600px) {{
        .card {{ padding:20px; }}
        .header h1 {{ font-size:23px; }}
    }}
</style>
</head>
<body>
<div class="container">
    <header class="header">
        <div class="logo">!</div>
        <h1>Simulação concluída</h1>
        <p>Você acabou de participar de uma simulação acadêmica de phishing.</p>
    </header>

    <section class="card">
        <div class="danger">
            <strong>Esta não era uma página de login real.</strong><br><br>
            O objetivo desta atividade é demonstrar como uma página aparentemente
            legítima pode ser utilizada em uma tentativa de engenharia social.
        </div>
        <div class="success">
            <strong>Etapa registrada com sucesso.</strong><br>
            A aplicação registrou a participação no banco de dados local
            utilizado pelo laboratório.
        </div>
        <h2>Informação utilizada na simulação</h2>
        <div class="email-box">{email_seguro}</div>
    </section>

    <section class="card center">
        <a href="/" class="button">Voltar ao início</a>
    </section>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def _send_content(self, content, content_type="text/html; charset=utf-8", status=200):
        body = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _ler_corpo_formulario(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8")
        campos = parse_qs(corpo)
        return {k: v[0] for k, v in campos.items()}

    def _cookie_sessao(self):
        header = self.headers.get("Cookie", "")
        for parte in header.split(";"):
            if "=" in parte:
                nome, valor = parte.strip().split("=", 1)
                if nome == "sessao":
                    return valor
        return None

    def do_GET(self):
        if self.path in ["/", "/login.html"]:
            html_content = ler_arquivo("login.html")
            if html_content:
                self._send_content(html_content)
            else:
                self._send_content("<h1>Erro: login.html não encontrado</h1>", status=404)

        elif self.path == "/login.css":
            css_content = ler_arquivo("login.css")
            if css_content:
                self._send_content(css_content, content_type="text/css; charset=utf-8")
            else:
                self._send_content("/* CSS não encontrado */", status=404)

        elif self.path == "/resultado":
            token = self._cookie_sessao()
            email = SESSOES.get(token)
            if email is None:
                self._redirect("/")
                return
            self._send_content(pagina_resultado(email))

        elif self.path == "/teste":
            try:
                conn = get_db()
                conn.execute("SELECT 1")
                conn.close()
                self._send_content("<h1>CONEXAO OK!</h1><p><a href='/'>Voltar</a></p>")
            except sqlite3.Error as e:
                self._send_content(
                    f"<h1>ERRO NA CONEXAO</h1><pre>{escape(str(e))}</pre>",
                    status=500,
                )
        else:
            self._send_content("<h1>404 - Não encontrado</h1>", status=404)

    def do_POST(self):
        if self.path != "/post":
            self._send_content("<h1>404 - Não encontrado</h1>", status=404)
            return

        dados = self._ler_corpo_formulario()
        email = dados.get("email", "").strip()
        senha = dados.get("senha", "")

        if not email or not senha:
            self._redirect("/")
            return

        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (login, senha) VALUES (?, ?)",
            (email, senha),
        )
        conn.commit()
        conn.close()

        token = secrets.token_hex(16)
        SESSOES[token] = email

        self.send_response(303)
        self.send_header("Location", "/resultado")
        self.send_header("Set-Cookie", f"sessao={token}; Path=/; HttpOnly")
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    init_db()
    servidor = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Servidor rodando em http://localhost:{PORT}")
    servidor.serve_forever()