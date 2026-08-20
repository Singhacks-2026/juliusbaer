# Julius Baer — Wealth Intelligence

> **From Portfolio Monitoring to Intelligence: Reimagining Wealth Advisory** — Build an AI-powered wealth intelligence experience that transforms traditional portfolio monitoring into proactive, personalised, and explainable advisory insights.

---

## Challenge Summary

**Goal**: Design a next-generation digital wealth advisory experience that helps Relationship Managers understand **what is happening in a client's portfolio → what could happen next → what actions should be considered**.

**Build path**: Create an AI-powered wealth intelligence layer that continuously monitors portfolios, identifies risks and opportunities, generates personalised recommendations, and supports better RM-client conversations.

> **📖 IMPORTANT**: Before starting your build, please read this **README.md** first. It contains the challenge context, requirements, and guidance to help you build a strong solution.

---

## 📋 The Problem We're Solving

### Current State

* Julius Baer continues to modernise its digital channels while maintaining a relationship-driven private banking model
* Clients and Relationship Managers can already access portfolio valuations, performance, asset allocations, and market information digitally
* Existing tools are often **descriptive rather than advisory**
* RMs must manually interpret portfolio risks, market implications, tax considerations, and potential actions
* Wealth portfolios are increasingly complex across asset classes, jurisdictions, currencies, mandates, and client objectives

There is an opportunity to create an **AI-powered wealth intelligence layer** that helps RMs understand and explain portfolio performance, anticipate potential developments, and identify actions worth considering.

### What You're Building

A next-generation digital experience that transforms traditional portfolio dashboards into an **intelligent advisory companion**.

The solution should go beyond portfolio visualisation and provide:

* Intelligent portfolio explanations
* AI-generated risk insights
* Personalised recommendations
* Rebalancing suggestions
* Tax-aware optimisation opportunities
* Event-driven investment ideas
* Portfolio stress testing and scenario analysis
* RM-ready client insights

### Who Benefits

* **Primary users**: Relationship Managers
* **Clients**: More timely, personalised, and informed advisory conversations
* **Internal stakeholders**: Product, digital-channel, technology, risk, and compliance teams evaluating how such a solution could fit into the Julius Baer ecosystem

---

## 🎯 What You're Building

The challenge is to move from:

> **"What does my client's portfolio look like?"**

to:

> **"What should I know, and what should I do next?"**

```text
┌──────────────────────────────────────────────────────────────┐
│                       Client Context                         │
│ Portfolio • Mandate • Risk Profile • Tax • Goals • Events   │
└────────────────────────────┬─────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│                  AI Wealth Intelligence Layer                │
│   Monitor • Analyse • Explain • Recommend • Stress Test      │
└────────────────────────────┬─────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│                   RM Intelligence Workbench                  │
│      Prioritise • Review • Prepare • Compare • Decide        │
└────────────────────────────┬─────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│                    Client Advisory Action                    │
│              Discuss • Rebalance • Plan • Act                │
└──────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Key Capabilities

### 1. AI Wealth Copilot

Continuously monitor portfolios and proactively surface meaningful observations for Relationship Managers.

### 2. Intelligent Risk Alerts

Identify portfolio drift, concentration, liquidity, currency, and other relevant client-specific risks.

### 3. Personalised Recommendations

Generate recommendations based on portfolio composition, investment mandate, risk profile, geographic exposure, tax considerations, market conditions, and client objectives.

### 4. Rebalancing Recommendations

Identify portfolio inefficiencies and suggest potential actions while explaining why a rebalance may be relevant.

### 5. Tax-Aware Optimisation

Surface potential tax considerations and optimisation opportunities relevant to portfolio decisions.

### 6. Event-Based Opportunity Engine

Connect market developments and external events to affected client portfolios and surface relevant investment opportunities or risks.

### 7. Portfolio Stress Testing & Scenario Analysis

Allow RMs to understand how different market scenarios could affect a client's portfolio and explore possible responses.

### 8. Life-Event Wealth Planning

Incorporate client objectives and life events such as retirement, sale of a business, philanthropy, education funding, and succession planning.

### 9. RM Intelligence Workbench

Provide RMs with a central view of actionable client intelligence to improve preparation, prioritisation, productivity, and client engagement.

---

## 🧠 Intelligence Inputs

The solution should demonstrate how personalised insights can be generated using relevant client and market context.

Potential inputs include:

* Portfolio composition
* Investment mandate
* Risk profile
* Geographic exposure
* Currency exposure
* Tax considerations
* Market conditions
* Client objectives
* Client life events

The objective is not simply to display more data, but to identify **what matters to the RM and why**.

---

## 🔄 Example Advisory Flow

```text
Portfolio / Market Signal
          ↓
AI Detects Relevant Change
          ↓
Assess Client-Specific Impact
          ↓
Generate Explanation or Alert
          ↓
Recommend Potential Actions
          ↓
RM Reviews Insight
          ↓
Client Conversation / Advisory Action
```

A strong solution should demonstrate how the RM moves from **signal → understanding → decision → client engagement**.

---

## 🛡️ Trust, Governance & Explainability

AI-driven wealth advisory must preserve trust and the central role of the Relationship Manager.

Participants should consider:

* **Explainability** — Why was an insight or recommendation generated?
* **Suitability** — Does it consider the client's mandate, risk profile, and objectives?
* **Human oversight** — Can the RM review, reject, or modify recommendations?
* **Traceability** — Can supporting data and assumptions be inspected?
* **Compliance** — Could the workflow operate within a regulated banking environment?
* **Security** — How would sensitive client and portfolio information be protected?

Recommendations should support **human decision-making rather than replace it**.

---

## 📊 Data

Julius Baer-provided datasets and supporting materials are xyz

* Portfolio holdings and performance
* Investment mandates
* Client risk profiles
* Market data
* Currency information
* Client objectives
* Relevant market events

Specific datasets provided for the challenge will be communicated separately.

---

## 🛠️ Technology

Participants are free to use **any technology stack, APIs, AI models, frameworks, software, or hardware** suitable for their solution.

Solutions should consider how the proposed technology could realistically operate within a private banking environment, including:

* Security
* Scalability
* Data protection
* Integration
* Explainability
* Compliance

---

## 🏆 Judging Criteria

| Criteria                                | Weight | Description                                                                                                                                           |
| --------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Client-Centric Innovation**           | 25%    | Degree to which the solution addresses real private-banking client needs and differentiates Julius Baer's digital offering                            |
| **User Experience & Design**            | 25%    | Simplicity, clarity, and actionability of wealth insights                                                                                             |
| **Technical & Operational Feasibility** | 25%    | Realism of implementation within banking architecture, including security, scalability, and compliance                                                |
| **Strategic Impact**                    | 25%    | Potential to strengthen Julius Baer's position as a modern, tech-enabled wealth manager while preserving the central role of the Relationship Manager |

---

## ✅ Features Checklist

### Wealth Intelligence

* [ ] AI-powered portfolio monitoring
* [ ] Intelligent portfolio explanations
* [ ] Client-specific risk alerts
* [ ] Personalised recommendations
* [ ] RM-ready actionable insights

### Advisory Capabilities

* [ ] Rebalancing suggestions
* [ ] Tax-aware optimisation opportunities
* [ ] Event-driven portfolio intelligence
* [ ] Portfolio stress testing or scenario analysis
* [ ] Client objectives or life events incorporated

### Trust & Governance

* [ ] Explainable recommendations
* [ ] RM review and human oversight
* [ ] Suitability considerations
* [ ] Supporting evidence or assumptions
* [ ] Security and compliance considerations

---

## 🎤 Presentation & Demo

**Format**: Presentation + Demo

Your final presentation should include:

* Clear articulation of the problem
* Clear representation of the proposed solution
* Main functional highlights
* Explanation of how the solution addresses the challenge
* Demonstration of how AI-generated insights translate into RM actions
* Visual screens, journeys, diagrams, or charts where useful

The presentation should be **concise, comprehensive, and easy to follow**, with short descriptions where necessary.

---

## 🚀 Challenge North Star

> **Build the intelligence layer between portfolio data and the Relationship Manager.**

Help RMs understand what matters, anticipate what may happen next, and turn complex portfolio information into timely, personalised, and trustworthy advisory conversations.
