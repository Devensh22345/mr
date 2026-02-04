# Telegram Account Manager Bot

A powerful Telegram bot for managing multiple Telegram accounts with MongoDB database support.

## Features

### 🔐 Account Management
- Login multiple Telegram accounts with API ID/HASH
- Store session strings securely in MongoDB
- Support for 2FA accounts
- Account status monitoring (active/inactive/frozen)

### 👤 User Features
- `/login` - Add new accounts
- `/set` - User settings menu
  - View all accounts
  - Remove accounts (single/multiple/all)
  - Refresh account status
  - Set/remove log channel

### 👑 Admin Features
- `/admin` - Admin panel
  - View all users' accounts
  - Remove accounts (by user/numbers/all)
  - Refresh all accounts
  - Set string channel
  - Admin management (add/remove/list)
  - Account settings modification
  - Log channel management

### 📱 OTP Management
- `/otp` - View OTPs from all accounts
- Select specific account for OTP
- Check all accounts for new OTPs

### 📨 Message Sending
- `/send` - Send messages from all accounts
  - Send to bots
  - Send to users
  - Send to groups
  - Single or multiple messages
  - Support for text, photos, documents, videos

### 👥 Group Management
- `/join` - Join groups/channels
- `/leave` - Leave groups/channels
- Support for invite links, usernames, IDs

### 🚨 Reporting System
- `/report` - Report users/groups/channels/posts
- Multiple report reasons
- Custom descriptions
- Configurable reports per account
- Human-like behavior with random delays
- `/stop` - Stop reporting immediately

### ⚡ Utility Commands
- `/cancel` - Cancel current operation
- `/stop` - Stop reporting process
- Automatic logging to main log group

## Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd telegram_bot
