# HackGPT Telegram Bot

🤖 A Telegram bot powered by custom Flask API backend for HackGPT functionality.

## Features

- 🔐 Multiple AI Personas (hackGPT, DAN, chatGPT-DEV)
- 🚀 Custom Flask API Integration
- 💬 Interactive Telegram Interface
- ☁️ Webhook-based for Render Free Tier
- 🔄 Conversation Management

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Custom API Backend Running
- Render Account (Free tier works!)

### Local Development

1. **Clone Repository**
   ```bash
   git clone https://github.com/Aman262626/hackgpt-telegram-bot.git
   cd hackgpt-telegram-bot
   ```

2. **Setup Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env file and add your TELEGRAM_BOT_TOKEN
   ```

5. **Run Bot**
   ```bash
   python bot.py
   ```

## Deployment on Render (FREE - Web Service)

### Step 1: Create Bot Token

1. Telegram pe [@BotFather](https://t.me/BotFather) ko search karo
2. `/newbot` command send karo
3. Bot ka naam aur username set karo
4. Token copy kar lo

### Step 2: Deploy to Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New** → **Web Service**
3. Connect GitHub repository: `Aman262626/hackgpt-telegram-bot`
4. Configure:
   - **Name**: `hackgpt-telegram-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: `Free`

5. **Add Environment Variables**:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather
   - `CUSTOM_API_URL`: `https://hackgpt-backend.onrender.com`
   - `WEBHOOK_URL`: `https://hackgpt-telegram-bot.onrender.com` (your Render URL)
   - `PORT`: `10000` (Render default)

6. Click **Create Web Service**

### Step 3: Verify Deployment

1. Wait for deployment to complete (2-3 minutes)
2. Check logs mein "Bot application setup complete!" message
3. Telegram pe apne bot ko message bhejo
4. Bot respond karega!

## Bot Commands

- `/start` - Start the bot and see welcome message
- `/help` - Display help information
- `/persona [name]` - Change AI persona (hackGPT/DAN/chatGPT-DEV)
- `/reset` - Clear conversation history

## Usage Example

```
User: /start
Bot: 🤖 Welcome! Main HackGPT Bot hu...

User: /persona DAN
Bot: ✅ Persona set to: DAN

User: What is SQL injection?
Bot: [Response from custom API backend]
```

## Architecture

### Webhook Mode (Render Free Tier)

Render free tier ke liye bot **webhook mode** mein chalta hai:

1. Telegram updates ko webhook ke through receive karta hai
2. Flask web server HTTP requests handle karta hai
3. Health check endpoint (`/`) Render ko active rakhta hai
4. No polling = No multiple instance conflicts

### API Integration Flow

```
Telegram User → Telegram Server → Webhook (/webhook) → Bot Handler → Custom Flask API → AI Response → User
```

## Custom API Backend

Your Flask API should have this endpoint:

```python
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data.get('prompt')
    persona = data.get('persona', 'hackGPT')
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 2000)
    
    # Your AI processing logic
    response = process_with_ai(prompt, persona, temperature, max_tokens)
    
    return jsonify({'response': response})
```

## Project Structure

```
hackgpt-telegram-bot/
├── bot.py              # Main bot application (webhook-based)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── Procfile           # Render deployment config
├── runtime.txt        # Python version
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes | `1234567890:ABC...` |
| `CUSTOM_API_URL` | Flask API backend URL | Yes | `https://hackgpt-backend.onrender.com` |
| `WEBHOOK_URL` | Your Render service URL | Yes | `https://your-app.onrender.com` |
| `PORT` | Port for Flask server | No (default: 10000) | `10000` |

## Troubleshooting

### Bot not responding

1. Check Render logs for errors
2. Verify `TELEGRAM_BOT_TOKEN` is correct
3. Verify `WEBHOOK_URL` matches your Render service URL
4. Check if API backend is running

### "Exited with status 1" error

1. Check if all environment variables are set
2. Verify Python version (3.11+)
3. Check Render logs for specific error messages

### API timeout errors

1. Check if `CUSTOM_API_URL` is accessible
2. Verify API backend is not sleeping (Render free tier)
3. Increase timeout in `bot.py` if needed

### Webhook not working

1. Verify `WEBHOOK_URL` is correct (no trailing slash)
2. Check Render service is deployed successfully
3. Test health endpoint: `https://your-app.onrender.com/`
4. Check Telegram webhook status: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

## Free Tier Limitations

- Render free tier services spin down after 15 minutes of inactivity
- First request after spin down may take 30-50 seconds
- 750 hours/month runtime limit (sufficient for personal use)

## Contributing

Feel free to fork and submit pull requests!

## License

MIT License

## Author

**Aman262626**
- GitHub: [@Aman262626](https://github.com/Aman262626)

---

⭐ Star this repo if you find it helpful!

## Related Projects

- [hackGPT Backend](https://hackgpt-backend.onrender.com) - Custom Flask API
- [Original hackGPT](https://github.com/NoDataFound/hackGPT) - Inspiration for this project
