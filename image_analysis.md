# Image Analysis: Huvo AI — Forward Deployed Engineer Assignment

The three screenshots (`Screenshot_2026-08-23_23-24-52.png`, `Screenshot_2026-08-23_23-24-59.png`, `Screenshot_2026-08-23_23-25-03.png`) are sequential pages of a single PDF/document: a take-home assignment brief from **Huvo AI** for a **Forward Deployed Engineer** role.

## Page 1 (23-24-52): Objective & Scenario

- **Deadline:** 24 hours
- **Mandatory backend:** FastAPI (Python) — Express.js or other frameworks not accepted
- **Objective:** Build a simple AI conversational bot for a fictional real-estate company. Focus is on **prompt engineering and agent behaviour**, with a prompt that works across both chat and voice/calling interactions.
- **Scenario:** AI sales agent for **Northstar Homes**, project **Northstar One**, located in **Sector 79, Gurugram**.
  - Configurations: 2 BHK and 3 BHK
  - Starting price: 2 BHK ₹1.35 crore onwards; 3 BHK ₹1.75 crore onwards
  - Agent must communicate naturally in **English, Hindi, and Hinglish**, understand customer requirements, answer questions, qualify leads, and help arrange a site visit.
- **Part 1 — Prompt:** Create a strong system prompt handling: natural conversation, customer qualification, multilingual support, common objections, busy/uninterested customers, requests to contact later, requests to stop communication, unknown questions, site-visit booking, booking failures, human escalation, and proper conversation ending. The agent must not invent prices, discounts, availability, or unprovided information.

## Page 2 (23-24-59): Simple Bot & Submission Requirements

- **Part 2 — Simple Bot:** Build a simple text-based conversational bot with a basic web interface using the final prompt (backend must be FastAPI). The bot should:
  - Accept messages, respond via the final prompt, remember conversation context
  - Support English/Hindi/Hinglish
  - Handle different intents/objections, simulate site-visit booking (including failed bookings)
  - Generate post-conversation analytics (budget, interest level, configuration, site-visit status, follow-up requirement, etc.)
  - Include test cases showing input, expected behavior, and actual output
- **Submission requirements:**
  1. **Public GitHub repo** with: final prompt, source code, README, `.env.example` (no committed secrets)
  2. **Demo video** (Loom/Drive/unlisted YouTube) showing the bot working, a sample conversation, prompt approach, and implementation explanation
  3. **README** covering: how to run the bot, key assumptions, known limitations, AI tools used

## Page 3 (23-25-03): Submission Contact & Evaluation Criteria

- **Send submission to:**
  - To: `aditi@huvo.ai`
  - CC: `nikhil@huvo.ai`, `vaibhav@huvo.ai`, `rohit@huvo.ai`
  - Include: GitHub repo link, demo video link, relevant notes
- **Evaluation criteria:** prompt quality, agent behaviour, handling of different customer situations, conversation context/memory, whether the bot works, code clarity, and understanding of the solution.
- Selected candidates will be invited for an interview.

## Summary

The three images together form the complete assignment spec for a job candidate: build a bilingual (Hindi/English/Hinglish) real-estate sales chatbot with a FastAPI backend, strong system prompt, and simple web UI, then submit it via GitHub + demo video to Huvo AI's hiring team within 24 hours.
