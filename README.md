# Pinterest Growth Agents (complete: Phase 1-4)
Free, cloud (GitHub Actions), phone-only setup. Website **read-only**. **Dry-run ON** by default: jab tak tum band na karo kuch publish nahi hota.
Koi guarantee nahi ke traffic/ranking barhegi ya Pinterest action nahi lega. Spam-risk score risk kam karta hai, "100% safe" nahi.

## Kya kaun karta hai
Tum (ek dafa): accounts, 23 boards, keys/tokens, secrets. Baqi sab agents: pins banana, Main Board par publish, apne pins tool boards mein save, curator, analytics, reports.
Jo agents nahi kar sakte (API/policy), wo **numbered task list** (2-3 min) mein aata hai. Kuch fake nahi hota.

## Sach: kya API se ho sakta hai (docs se verify kiya)
- Pin banana `POST /v5/pins`, save `POST /v5/pins/{id}/save`, search `GET /v5/search/pins`, sandbox: official docs/changelog mein hain.
- **Trial access par kya allowed hai ye verify NAHI ho saka.** Har call ka error handle hota hai (fallback ya manual task).
- **Follow-user**: official v5 endpoint nahi mila -> follows hamesha manual task list mein.
- Link-less pin, image_base64 upload, pin analytics: docs page se verify nahi hua; pehla live run/sandbox batayega, warna Mode B.
- Multi-image carousel/video Class I: abhi nahi banaye (sirf single-image tips/steps/cheatsheet). Ye Mode A/B dono mein.
- **Mode B** (default): system har din kal ke liye images + `pins.csv` banata hai; tum Pinterest par bulk upload karte ho (roz 2-3 min). **Mode A**: API se auto-publish (approved app chahiye). `pinterest.mode` badlo.
- Slots hourly check hote hain: pin slot ke baad agle ghante ke andar publish hoti hai (exact minute nahi).

## Setup (phone browser) - 12 steps
1. **GitHub**: github.com > Sign up. New repository `pinterest-growth-agents`, **Public** (Actions free; secrets safe; state branch mein tokens encrypted hote hain).
2. Repo > **Add file > Upload files** > sirf `pinterest-growth-agents.zip` > Commit.
3. Repo > **Add file > Create new file**, naam: `.github/workflows/agents.yml`, `agents.yml` file ka text paste karo > Commit. (Ye ek hi file poori automation hai. GitHub token workflow files khud push nahi kar sakta, isliye haath se.)
4. Repo > **Actions** > "Agents" > **Run workflow** > command `unpack` > Run. (baqi files repo mein aa jayengi)
5. **Gemini key**: aistudio.google.com > Get API key. Secret `GEMINI_API_KEY`.
6. Repo > **Settings > Secrets and variables > Actions > New repository secret**: `GEMINI_API_KEY`, `STATE_KEY` (koi lamba random phrase, yaad rakho). Optional: `GROQ_API_KEY`, `NTFY_TOPIC` (ntfy app mein random naam), `SMTP_USER`, `SMTP_APP_PASSWORD`, `NOTIFY_EMAIL_TO` (Gmail > Security > 2-Step > App passwords).
7. **GitHub mobile app** install, login, notifications on (alerts Issues ke zariye push aati hain).
8. Actions > Agents > Run workflow > **test-notify**. Issue/email aaye to theek. (Pakistan se kaun sa channel chalta hai ye tum test karke batao, mujhe verify nahi hua.)
9. Actions > Agents > **weekly**. `data/tools.json` banega + Pinterest rules summary. Issues mein report dekho; galat slugs `data/tools_seed.json` mein theek karo (pencil icon), phir weekly dobara.
10. **Pinterest**: Business account (pinterest.com > Sign up > Business). **23 boards** banao: `Main Board` + har tool ke naam ka board (tool ka exact naam, jaise "Merge PDF"). Boards khud banane hain, system nahi banata.
11. **Pinterest developer** (Mode A ke liye): developers.pinterest.com > Create app > Trial access request. Approval mein waqt lag sakta hai. Tab tak Mode B chalao. App ID/Secret aur refresh token mile to secrets: `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, `PINTEREST_REFRESH_TOKEN` (ya `PINTEREST_ACCESS_TOKEN`). Phir Actions > Agents > **board-check**: mapping dikhata hai; Main Board ID aur `tools:` block `config/settings.yaml` mein paste karo.
12. **GA4** (dashboard): analytics.google.com > Admin > Create property > Data stream (Web, site URL) > Measurement ID Blogger ke Settings mein daalo (Blogger > Settings > Google Analytics; ye site ka setting hai jo tum khud karte ho, agents website ko kabhi nahi chhoote). Google Cloud console > naya project > "Google Analytics Data API" Enable > Service Account banao > JSON key download. GA4 Admin > Property access management > service account ka email **Viewer** add karo. Secrets: `GA4_PROPERTY_ID` (number), `GA4_SERVICE_ACCOUNT_JSON` (poori JSON paste). Naye property ko 24-48 ghante data mein lagte hain.
13. Repo > **Settings > Pages** > Deploy from branch > `main` / root. Dashboard: `https://<username>.github.io/pinterest-growth-agents/dashboard/analytics.html` (bookmark). Agar update na ho to repo mein `dashboard/analytics.html` bhi dekh sakte ho.

## Live jaane se pehle
Dry-run reports 2-3 din dekho (Issues mein + repo ka `previews/` folder: images aur pins.csv). Theek lage to Actions > Agents > **dry-run-off**. LIVE ke liye rules-check ka ho chuka hona zaroori hai (weekly ye kar deta hai).

## Roz ka control
- Numbers/times: `config/settings.yaml` > pencil > Commit. Agle run se lagu. Ceiling se upar ho to safe value + wajah report mein.
- Pause/Resume: Actions > Agents > Run workflow > `pause` / `resume`, ya kisi Issue par comment `/pause` `/resume` `/status` (chalne mein ~1 min lagta hai; sirf repo owner ki comment maani jati hai).
- Curator: `curator.enabled: true` aur chhote numbers. Follows hamesha manual; saves API se ya manual task list.
- Auto-pause: warning, 401, bar bar 403/429, impressions ka bara girna. Alert mein cause + steps hote hain. Resume ke baad activity kam rehti hai.

## Actions minutes (andaza)
tick ~14x/din x ~1 min + daily + weekly + monitor = ~600-700 min/mahina. Public repo: standard runners free.

## Services (koi card nahi)
GitHub, Gemini AI Studio (free tier), Groq (optional), GA4 + Google Cloud API (service account; Google Cloud kabhi card maang sakta hai - GA4 Data API ke liye normally free project chalta hai, agar card maange to google.enabled: false rakho), Pinterest developer, Gmail App Password/ntfy (optional). Telegram sirf optional (VPN).

## Files
`config/` settings + policies | `src/agents/` strategist, creator, manager, curator, analytics, reporter, site_knowledge | `src/core/` orchestrator, compliance, risk, scheduler, db, llm, healing | `src/integrations/` pinterest, ga4, site_reader, notify | `src/images/` generator | `dashboard/` | `tests/` (offline).
Website: sirf public GET (robots.txt respect). Koi write path nahi hai.
