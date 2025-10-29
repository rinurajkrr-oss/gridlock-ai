import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# -------------------------------------------------
# 1️⃣ Load the trained model
# -------------------------------------------------
model_path = "C://Users//rinur//OneDrive//Desktop//Gridlock_system//gridlock_model.pkl"

try:
    model = joblib.load(model_path)
    print("✅ Model loaded successfully using joblib!\n")
except Exception as e:
    print("❌ Error loading model:", e)
    exit()

# -------------------------------------------------
# 2️⃣ Load your test dataset
# -------------------------------------------------
data_path = "C://Users//rinur//OneDrive//Desktop//Gridlock_system//gridlock_dataset.csv"

try:
    data = pd.read_csv(data_path)
    print(f"✅ Test data loaded successfully! Shape: {data.shape}\n")
except Exception as e:
    print("❌ Error loading test data:", e)
    exit()

# -------------------------------------------------
# 3️⃣ Prepare features and labels
# -------------------------------------------------
feature_cols = ['Voltage', 'Current', 'Power', 'Power_Factor']
label_col = 'Label'


if not all(col in data.columns for col in feature_cols + [label_col]):
    print("❌ Error: Required columns not found in dataset.")
    print("Available columns:", list(data.columns))
    exit()

X_test = data[feature_cols]
y_test = data[label_col]

# -------------------------------------------------
# 4️⃣ Run predictions
# -------------------------------------------------
y_pred = model.predict(X_test)

# -------------------------------------------------
# 5️⃣ Evaluate performance
# -------------------------------------------------
accuracy = accuracy_score(y_test, y_pred)
print(f"🎯 Model Accuracy: {accuracy * 100:.2f}%\n")
print("Classification Report:\n", classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
