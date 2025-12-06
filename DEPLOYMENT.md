# Voice Assistant Deployment Guide

## Deploy to Render (Recommended)

Render is recommended for Python Flask apps with WebSocket support.

### Step 1: Push Code to GitHub
Make sure your `price_prediction` folder is in your GitHub repository.

### Step 2: Create New Web Service on Render
1. Go to https://render.com and sign in
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:

   **Settings:**
   - Name: `krushi-voice-assistant`
   - Region: Choose closest to your users
   - Branch: `main` (or your default branch)
   - Root Directory: `price_prediction`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT priceAndVoice:app`

### Step 3: Environment Variables
Add the following environment variable in Render dashboard:
- Key: `GEMINI_API_KEY`
- Value: Your actual Gemini API key

### Step 4: Deploy
Click "Create Web Service" and wait for deployment (5-10 minutes).

### Step 5: Get Your Production URL
After deployment, Render will provide a URL like:
`https://krushi-voice-assistant.onrender.com`

### Step 6: Update Frontend
Update `frontend/src/components/ui/VoiceAssistantButton.jsx`:
- Change `http://localhost:5002` to your Render URL
- Example: `https://krushi-voice-assistant.onrender.com`

---

## Alternative: Deploy to Railway

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login and Initialize
```bash
cd price_prediction
railway login
railway init
```

### Step 3: Set Environment Variables
```bash
railway variables set GEMINI_API_KEY=your_api_key_here
```

### Step 4: Deploy
```bash
railway up
```

### Step 5: Get Domain
```bash
railway domain
```

---

## Important Notes

1. **Free Tier Limitations:**
   - Render free tier: Service sleeps after 15 minutes of inactivity
   - Railway: $5/month credit required for always-on service
   - First request after sleep may take 30-60 seconds

2. **Audio Processing:**
   - Voice assistant requires microphone access (browser permission)
   - gTTS and pygame work on cloud servers
   - Speech recognition may have slight latency

3. **WebSocket Support:**
   - Both Render and Railway support WebSockets
   - Ensure Socket.IO client connects to correct URL

4. **CORS Configuration:**
   - Already updated to include production frontend URL
   - No additional configuration needed

---

## Testing After Deployment

1. Check health: `https://your-url.onrender.com/`
   - Should return: "Flask server is running!"

2. Test recommendations: `https://your-url.onrender.com/recommendations`
   - Should return product recommendations

3. Test in frontend:
   - Open Voice Assistant
   - Check browser console for connection errors
   - Test voice interaction

---

## Troubleshooting

### Service won't start:
- Check Render/Railway logs for errors
- Verify all dependencies in requirements.txt
- Ensure Python 3.9+ is used

### Socket.IO connection failed:
- Verify CORS origins include your frontend URL
- Check browser console for errors
- Ensure WebSocket protocol is enabled

### Voice not working:
- Check browser microphone permissions
- Verify pygame and gTTS are installed
- Check server logs for audio processing errors

### Import errors:
- Verify protobuf==4.24.0 is installed
- Check all packages are in requirements.txt
- Review build logs for failed installations
