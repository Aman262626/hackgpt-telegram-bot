# HackGPT Telegram Bot

🤖 A Telegram bot powered by custom Flask API backend for HackGPT functionality.

## Features

- 🔐 Multiple AI Personas (hackGPT, DAN, chatGPT-DEV)
- 🚀 Custom Flask API Integration
- 💬 Interactive Telegram Interface
- ☁️ Ready for Render Deployment
- 🔄 Conversation Management

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Custom API Backend Running

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

## Deployment on Render

### Step 1: Prepare Repository

Repository is already configured with:
- `Procfile` - Render worker configuration
- `runtime.txt` - Python version specification
- `requirements.txt` - Dependencies

### Step 2: Deploy to Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `hackgpt-telegram-bot`
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: Free

5. Add Environment Variables:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather
   - `CUSTOM_API_URL`: `https://hackgpt-backend.onrender.com`

6. Click **Create Web Service**

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
├── bot.py              # Main bot application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── Procfile           # Render deployment config
├── runtime.txt        # Python version
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `CUSTOM_API_URL` | Flask API backend URL | Yes |

## Getting Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the token provided
5. Add token to `.env` file

## Troubleshooting

### Bot not responding
- Check if `TELEGRAM_BOT_TOKEN` is correctly set
- Verify API backend is running and accessible
- Check Render logs for errors

### API timeout errors
- Increase timeout value in `bot.py`
- Check API backend performance
- Verify network connectivity

## Contributing

Feel free to fork and submit pull requests!

## License

MIT License

## Author

**Aman262626**
- GitHub: [@Aman262626](https://github.com/Aman262626)

---

⭐ Star this repo if you find it helpful!
