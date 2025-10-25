# Booking System Setup Guide

## ✅ What's Working

The booking system is now fully functional with:
- Multi-turn conversation support (asks for missing info)
- Complete booking in one request
- Excel schedule updates
- Session management across conversation turns
- Doctor validation
- Slot availability checking

## 🎯 Current Features

### 1. **Book Appointments**
Users can book in two ways:

**Complete request:**
- "book appointment with Dr Mark tomorrow at 9:30 AM"

**Step-by-step:**
- User: "book appointment"
- Agent: "Which doctor would you like to book an appointment with?"
- User: "Dr Mark"
- Agent: "What date and time would you like to see Dr. Mark?"
- User: "tomorrow at 9:30 AM"
- Agent: "Appointment booked successfully!"

### 2. **Automatic Updates**
- Excel file is updated (slot marked as "Booked")
- Session cleared after successful booking
- Validates slot availability before booking

## 📧 Google Calendar Integration (Optional)

The system attempts to create Google Calendar events and send email invitations. To enable this:

### Setup Steps:

1. **Create OAuth 2.0 Credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials for "Desktop app"
   - Download as `google-credentials.json`

2. **First Run:**
   - When first booking is made, browser will open for authentication
   - Grant calendar access
   - Token saved in `token.pickle` for future use

3. **If Not Configured:**
   - Bookings still work (Excel updated)
   - Message: "Appointment booked successfully! Confirmation will be sent to {email}."
   - Calendar integration skipped gracefully

## 🧪 Testing

```python
# Test complete booking
"book appointment with Dr Mark tomorrow at 9:30 AM"

# Test step-by-step
"book appointment"
# Then follow prompts

# Verify booking
"is Dr Mark available tomorrow"
# Should show 9:30 AM slot is no longer available
```

## 📝 Dialogflow Configuration

Make sure your **Book Schedule** intent has:

**Training Phrases:**
- book appointment with @doctor on @date-time
- schedule @doctor at @date-time
- book appointment with @doctor
- book appointment
- schedule appointment

**Parameters:**
- doctor (required: false)
- date-time (required: false)

**Environment Variables:**
- CLINIC_EMAIL - Fixed email address for all appointment confirmations (set in .env file)

**Note:** Parameters are optional because the system handles multi-turn conversations.

## 🔄 Session Management

- Each conversation has a unique session_id
- Session persists across multiple messages
- Stores: doctor, datetime
- Email is read from CLINIC_EMAIL environment variable
- Cleared after successful booking
- Frontend maintains session_id automatically

## ✨ Next Steps (Optional Enhancements)

1. **Email Notifications:** Add SMTP email sending
2. **SMS Reminders:** Integrate Twilio
3. **Cancellation:** Add "cancel appointment" intent
4. **Rescheduling:** Add "reschedule appointment" intent
5. **Patient Database:** Store patient info for repeat bookings
