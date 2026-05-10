# Nexus ERP: Material Requirements Planning (MRP) Engine

Nexus ERP is a lightweight, high-performance Material Requirements Planning (MRP) calculation engine built with Python and Pandas. It features a beautifully designed, interactive web dashboard powered by FastAPI and Vanilla HTML/JS/CSS.

This project demonstrates the core business math that drives manufacturing. By analyzing a current inventory database, a Manufacturing Bill of Materials (mBOM), and a customer order forecast, the engine dynamically calculates exactly *how many* raw materials need to be ordered and *when* they must be ordered, strictly accounting for supplier lead times.

## 🌟 Features

- **Core MRP Engine (Pandas)**: 
  - **Low-Level Code (LLC) Algorithms**: Dynamically processes multi-tier mBOM structures from finished goods down to raw materials.
  - **Lot-for-Lot Sizing**: Calculates net requirements by accurately consuming current on-hand inventory chronologically.
  - **Lead Time Offsets**: Precisely propagates planned order release dates backwards based on specific item lead times.
- **FastAPI Backend**: Exposes lightning-fast REST API endpoints to trigger MRP runs and update inventory on the fly.
- **Interactive Web Dashboard**:
  - Premium dark-mode aesthetics utilizing glassmorphism.
  - **Inventory Management Module**: Dynamically edit stock levels directly from the UI.
  - Real-time simulation: Instantly visualize how inventory changes cascade through the entire multi-level purchase order schedule.
- **Automated CI/CD**: Fully configured GitHub Actions workflow (`.github/workflows/ci.yml`) handling automated `pytest` and linting on every push and PR.

## 📁 Project Structure

```text
mrp_calculator/
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI pipeline
├── src/
│   ├── api.py               # FastAPI backend application
│   ├── db_setup.py          # SQLite database generation & mock data
│   └── mrp_engine.py        # Core Pandas MRP calculation logic
├── static/                  # Frontend assets
│   ├── index.html           # Dashboard UI
│   ├── style.css            # Premium glassmorphism styling
│   └── app.js               # API interaction and dynamic DOM updates
├── tests/
│   └── test_mrp.py          # Pytest suite with isolated in-memory DB tests
├── requirements.txt         # Project dependencies
└── .gitignore               # Git ignore rules
```

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- `pip`

### Installation

1. **Clone the repository:**
   ```bash
   git clone git@github.com:kangkabseok2021/mrp_calculator.git
   cd mrp_calculator
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the Database:**
   Generate the SQLite database (`mrp_database.db`) populated with the "Mountain Bike" mock dataset:
   ```bash
   python src/db_setup.py
   ```

## 💻 Usage

To run the interactive ERP Dashboard:

1. **Start the FastAPI server:**
   ```bash
   cd src
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

2. **Open your browser:**
   Navigate to `http://localhost:8000` to interact with the Nexus ERP dashboard.

3. **Simulate Scenarios:**
   - Go to the **Inventory Manager** tab.
   - Edit the stock quantity for an item (e.g., set Spokes to 0).
   - Switch to the **MRP Engine** tab.
   - Click **Run MRP** to see the newly generated purchase order schedule adapt in real-time.

## 🧪 Testing

The logic of the MRP Engine is covered by comprehensive unit tests.

To run the test suite locally:
```bash
pytest tests/
```
