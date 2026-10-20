# E-mails do Supabase Auth

Cole cada arquivo em **Supabase → Authentication → Emails → Templates** (aba *Source* / HTML) e ajuste o *Subject*:

| Template no Supabase | Arquivo | Subject |
|---|---|---|
| **Confirm sign up** | `confirm-signup.html` | `Confirm your email for Gamefy` |
| **Reset password** | `reset-password.html` | `Reset your Gamefy password` |

Requisitos:
* **Authentication → URL Configuration → Site URL** = `https://gamefyapp.netlify.app` (os links usam `{{ .SiteURL }}`).
* Os links apontam para `/confirm-email?token_hash=…` e `/reset-password?token_hash=…`. O token só é consumido quando a pessoa aperta o botão
  na nossa página, então scanners de e-mail que abrem o link antes não o invalidam. **Não volte para `{{ .ConfirmationURL }}`.**
* Confirmar e-mail já deixa o usuário logado (cookies HttpOnly).

Detalhes de compatibilidade: layout em tabelas com CSS inline (Gmail/Outlook), modo escuro via `prefers-color-scheme` (Apple Mail/iOS),
sem imagens externas (não são bloqueadas), botão como link estilizado, preheader oculto, link alternativo em texto.
Para traduzir, edite só os textos; mantenha as variáveis `{{ .Email }}`, `{{ .SiteURL }}` e `{{ .TokenHash }}`.
