# Tomato Leaf Disease Classifier — টেকনিক্যাল ওভারভিউ

## উদ্দেশ্য (Purpose)
এটা একটা সিঙ্গেল-পেজ Streamlit ইনফারেন্স অ্যাপ, যেটা টমেটো পাতার ছবি দিয়ে ৪টা ক্লাসের
মধ্যে একটা প্রেডিক্ট করে, এবং সাথে Grad-CAM saliency overlay দেখায় (মডেল কেন এই
সিদ্ধান্ত নিলো সেটা বোঝানোর জন্য — interpretability)।

## আর্কিটেকচার
```
Browser (Streamlit UI)
   │  file_uploader (jpg/png)
   ▼
App.py (একটাই ফাইলে পুরো অ্যাপ, কোনো আলাদা backend/API লেয়ার নেই)
   │
   ├─ PIL: decode → RGB-তে convert → 224×224 resize
   ├─ np.array (float32) → predict()
   │        └─ model/model.keras (Keras CNN, @st.cache_resource দিয়ে singleton)
   │             → 4 ক্লাসের উপর softmax
   ├─ argmax → predicted_class, confidence (সর্বোচ্চ softmax প্রব্যাবিলিটি)
   └─ tf-keras-vis Gradcam(model, ReplaceToLinear, clone=True)
            └─ CategoricalScore(predicted_class_index)
            → cam heatmap → cm.jet colormap → cv2.addWeighted overlay
```

## App.py-এর গুরুত্বপূর্ণ ডিটেইলস
- **মডেল লোডিং**: `get_model()` ফাংশনটা `@st.cache_resource` দিয়ে wrap করা — মানে
  পুরো সার্ভার প্রসেসে একবারই লোড হয়, প্রতিটা রিকোয়েস্ট/rerun-এ না।
- **ক্লাসগুলো**: `["Early Blight", "Healthy", "Late Blight", "Leaf Spot"]` — এই
  ইনডেক্স অর্ডারটা খুব গুরুত্বপূর্ণ (load-bearing), মডেল ট্রেনিং/এক্সপোর্টের সময়
  যে অর্ডারে ছিল, ঠিক সেই অর্ডারের সাথে ম্যাচ করতে হবে।
- **প্রিপ্রসেসিং**: 224×224×3-এ resize, float32-এ cast। App.py-তে explicit কোনো
  normalization (যেমন `/255`) নেই — এর মানে normalization মডেলের ভিতরেই বেক করা
  আছে (যেমন একটা `Rescaling` লেয়ার), নাহলে ইনফারেন্সের সময় ইনপুট [0,255] রেঞ্জেই
  থেকে যাবে যেটা ভুল রেজাল্ট দিতে পারে।
- **ইনফারেন্স**: `model.predict(img_array, verbose=0)` — একটা সিঙ্গেল ইমেজ
  (rank 3) হলে `np.expand_dims` দিয়ে batch dimension যোগ করা হয়।
- **Explainability**: Grad-CAM কম্পিউট হয় `penultimate_layer=-1`-এ (GAP/dense
  হেডের ঠিক আগের শেষ conv লেয়ার), এটা gradient-based — মডেলকে clone করে output
  activation-কে linear-এ swap করা হয় (`ReplaceToLinear`) যাতে softmax-এর কারণে
  gradient saturate না হয়।
- **UI ফ্লো**: আপলোড → প্রিভিউ (400px resize করা) → এক্সপ্লিসিট "Predict" বাটন
  (আপলোড করলেই অটো-ট্রিগার হয় না) → প্রেডিকশন + কনফিডেন্স টেক্সট → 2-কলাম লেআউটে
  raw heatmap আর image/heatmap overlay (0.6/0.4 alpha blend)।

## টেক স্ট্যাক
| লেয়ার | টেকনোলজি |
|---|---|
| UI/সার্ভিং | Streamlit |
| মডেল | TensorFlow/Keras CNN (`model/model.keras`, ~93MB) |
| Interpretability | tf-keras-vis (Grad-CAM) |
| ইমেজ অপারেশন | Pillow (decode/resize), OpenCV (overlay blend), Matplotlib (jet colormap) |
| নিউমেরিক্স | NumPy |

## প্রজেক্ট লেআউট
```
App.py              # পুরো অ্যাপ্লিকেশন লজিক (~103 লাইন, কোনো মডিউল/টেস্ট নেই)
requirements.txt     # streamlit, tensorflow, pillow, numpy, tf-keras-vis, opencv-python, matplotlib
model/model.keras    # ট্রেইনড CNN, রানটাইমে লোড হয়
sample/{class}/      # প্রতিটা ক্লাসের উদাহরণ ছবি, ম্যানুয়াল টেস্টিং-এর জন্য
install.bat, run.bat # Windows কনভেনিয়েন্স স্ক্রিপ্ট (pip install -r ..., streamlit run App.py)
index.html, _config.yml  # GitHub Pages ল্যান্ডিং পেজ (অ্যাপ থেকে আলাদা)
```

## উল্লেখযোগ্য বিষয় / ঝুঁকি (Risks)
- কোনো automated test নেই — ভেরিফিকেশন এখনো ম্যানুয়াল (একটা sample ছবি আপলোড করে
  প্রেডিকশন আর heatmap চোখে দেখে চেক করা হয়)।
- Streamlit-এর `type=["jpg","jpeg","png"]` ফিল্টার ছাড়া তেমন কোনো input
  validation নেই; কোডে কোনো size cap নেই (README-তে 200MB বলা আছে, ওটা আসলে
  Streamlit-এর নিজস্ব ডিফল্ট লিমিট)।
- সিঙ্গেল-ফাইল অ্যাপ: UI, প্রিপ্রসেসিং, ইনফারেন্স, আর explainability — সব একসাথে,
  আলাদা করা নেই। এই স্কেলে ঠিক আছে, কিন্তু ভবিষ্যতে যদি বাড়ে (batch inference,
  API mode, একাধিক মডেল), তখন এগুলো আলাদা করা দরকার হবে।
- প্রতিটা প্রেডিকশনেই Grad-CAM সিঙ্ক্রোনাসলি রিকম্পিউট হয় (কোনো caching নেই) —
  একটা ইন্টারঅ্যাকটিভ সিঙ্গেল-ইমেজ ইউজকেসের জন্য ঠিক আছে, কিন্তু batch/throughput
  সিনারিওতে স্কেল করবে না।
- মডেল ফাইলটা (93MB) সরাসরি রিপোতে কমিট করা, external storage/registry থেকে
  fetch করা হয় না — ছোট প্রজেক্টের জন্য ঠিক আছে, মডেল বড় হলে বা ভার্সন বাড়লে
  এটা নিয়ে আবার ভাবা দরকার হবে।

---

# Admin Dashboard — আর্কিটেকচার ডিজাইন

## উদ্দেশ্য
প্রতিটা prediction (কে করলো, কোন ক্লাস predict হলো, কনফিডেন্স কত) DB-তে লগ করে,
একটা admin dashboard-এ মোট prediction সংখ্যা, ক্লাস distribution, আর confidence
distribution/average দেখানো। ground-truth ভিত্তিক accuracy ট্র্যাক করা হবে না
(মডেল সঠিক ছিল কিনা যাচাই করার কোনো feedback loop নেই) — শুধু confidence-ভিত্তিক
মেট্রিক্স।

## সিদ্ধান্ত নেওয়া স্কোপ
| প্রশ্ন | সিদ্ধান্ত |
|---|---|
| Storage | PostgreSQL/MySQL |
| Accuracy ট্র্যাকিং | ground truth নেই, শুধু confidence ট্র্যাক করা হবে |
| Access | মাল্টি-ইউজার লগইন, ২টা রোল (admin, regular user) |
| Dashboard টেক-স্ট্যাক | Streamlit multi-page app (আলাদা backend/framework না) |
| প্রথম ভার্সনের মেট্রিক্স | মোট count, ক্লাস distribution, confidence distribution/average, recent predictions টেবিল |
| আর্কিটেকচার অ্যাপ্রোচ | Approach A: Direct DB integration (App.py সরাসরি DB-তে লগ করবে) |

## হাই-লেভেল আর্কিটেকচার
```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│   main.py (entry, নতুন)      │     │  st.navigation (top navbar)   │
│   - Login gate               │     │  pages/admin_dashboard_page.py│
│   - role অনুযায়ী nav বানানো  │     │  pages/my_history_page.py     │
│ pages/predict_page.py:       │     │                                │
│     predict() হবার পরে       │     │  - role অনুযায়ী পেজ visible  │
│     log_prediction() কল ───┐ │     │    হবে/হবে না                 │
└─────────────────────────────┼─┘     └──────────────┬─────────────────┘
                              │                        │
                              ▼                        ▼
                    ┌────────────────────────────────────────┐
                    │        PostgreSQL (একই DB)              │
                    │  users, predictions টেবিল                │
                    └────────────────────────────────────────┘
```

**Auth**: কাস্টম bcrypt-ভিত্তিক auth (৩rd-party `streamlit-authenticator`
লাইব্রেরির বদলে) — কারণ ওই লাইব্রেরি নিজের YAML/config-ভিত্তিক user store
ব্যবহার করে, যেটা আমাদের DB-ভিত্তিক `users` টেবিলের (role ফিল্ডসহ) সাথে দুটো
আলাদা "sources of truth" তৈরি করতো। তার বদলে সরাসরি `bcrypt` দিয়ে hash/verify
করে, `users` টেবিলের বিপরীতে authenticate করা হবে (একই DB, একই role ফিল্ড)।
Login না করলে predict page-ও ব্যবহার করা যাবে না (predict করার আগেই gate থাকবে)।

**ইউজার প্রোভিশনিং**: প্রথম admin অ্যাকাউন্ট একটা seed script দিয়ে বানানো হবে
(manual DB insert, bcrypt-hashed password)। নতুন user সাইন-আপ ফর্ম এই স্কোপে নেই
— admin ম্যানুয়ালি ইউজার যোগ করবে (হয় সরাসরি DB-তে, নয়তো একটা ছোট CLI/script দিয়ে)।

## ডাটাবেস স্কিমা
```sql
users
├── id            SERIAL PRIMARY KEY
├── username       TEXT UNIQUE
├── password_hash  TEXT
├── role           TEXT   -- 'admin' | 'user'
└── created_at     TIMESTAMP

predictions
├── id              SERIAL PRIMARY KEY
├── user_id         FK → users.id
├── predicted_class TEXT      -- 'Early Blight' | 'Healthy' | 'Late Blight' | 'Leaf Spot'
├── confidence      FLOAT     -- 0-100
├── image_thumbnail BYTEA     -- ছোট thumbnail (recent-table এ দেখানোর জন্য)
└── created_at      TIMESTAMP
```

## পেজ স্ট্রাকচার + নেভবার
Streamlit-এর পুরনো automatic `pages/` ফোল্ডার ডিসকভারির বদলে `st.navigation()` +
`st.Page()` ব্যবহার হবে (Streamlit 1.59-এ available) — কারণ এতে **role অনুযায়ী
কোন পেজ দেখা যাবে সেটা কোডে কন্ট্রোল করা যায়** (admin না হলে Admin Dashboard পেজটাই
নেভবারে দেখাবে না), আর `position="top"` দিয়ে horizontal top navbar বানানো যায়
(ডিফল্ট sidebar নেভ-এর বদলে)।

```
main.py                          # আসল entry point
├── auth check (login না থাকলে শুধু login form)
├── role অনুযায়ী pages লিস্ট বানানো:
│     always:      predict_page, my_history_page
│     admin হলে +  admin_dashboard_page
└── st.navigation(pages, position="top").run()

pages/
├── predict_page.py             # বর্তমান App.py-এর predict + Grad-CAM লজিক (এখানে move হবে)
├── admin_dashboard_page.py     # শুধু role == 'admin' নেভবারে দেখা যাবে
└── my_history_page.py          # যেকোনো logged-in user, শুধু নিজের history

db.py                            # SQLAlchemy engine/session, connection setup
models.py                        # User, Prediction ORM models
auth_utils.py                    # bcrypt hash/verify + authenticate()/create_user()
repository.py                    # সব prediction-log / dashboard-query ফাংশন
imaging.py                       # thumbnail বানানোর হেল্পার
seed_admin.py                    # প্রথম admin অ্যাকাউন্ট বানানোর CLI স্ক্রিপ্ট
```

**নেভবার আইটেম (role অনুযায়ী):**

| আইটেম | Regular user | Admin |
|---|---|---|
| 🔬 Predict | ✅ | ✅ |
| 📜 My History | ✅ | ✅ |
| 📊 Admin Dashboard | ❌ | ✅ |
| 🚪 Logout | ✅ | ✅ |

Logout একটা `st.Page` না — top navbar-এর পাশে (`st.navigation` কল করার আগে,
sidebar বা page header-এ) আলাদা একটা বাটন হিসেবে থাকবে, ক্লিক করলে
`st.session_state` ক্লিয়ার করে login পেজে rerun করবে।

**App.py-এর ভবিষ্যৎ**: বর্তমান `App.py`-এর predict+Grad-CAM লজিক অপরিবর্তিত থেকে
`pages/predict_page.py`-তে move হবে; `main.py` হবে নতুন entry point (auth +
navigation শুধু)। `run.bat`/`install.bat`-এ `streamlit run App.py`-এর জায়গায়
`streamlit run main.py` করতে হবে।

## Admin Dashboard কম্পোনেন্ট (`1_Admin_Dashboard.py`)
1. **KPI cards (৩টা)**: মোট prediction সংখ্যা, গড় confidence, আজকের prediction সংখ্যা
2. **ক্লাস distribution** — bar/pie chart (৪টা ক্লাসের কতটা করে predict হয়েছে), Plotly/Altair দিয়ে
3. **Confidence distribution** — histogram (কনফিডেন্স কত রেঞ্জে বেশি পড়ে) + গড় কনফিডেন্স লাইন
4. **Recent predictions টেবিল** — শেষ ৫০টা: thumbnail, username, predicted class, confidence, timestamp (paginated `st.dataframe`)
5. **ফিল্টার**: ডেট রেঞ্জ + ক্লাস — উপরের সব chart/টেবিল-এ apply হবে

`2_My_History.py` — একই রকম, কিন্তু `WHERE user_id = current_user` ফিল্টার সহ, শুধু
নিজের prediction history + confidence trend দেখাবে।

## Integration point
বর্তমান [App.py:74-81](App.py#L74-L81)-এ যেখানে `predict()` কল হয়, এই ব্লকটা
অপরিবর্তিত অবস্থায় `pages/predict_page.py`-তে move হবে। ঠিক `predict()` কলের পরেই
`log_prediction(user_id, predicted_class, confidence, thumbnail)` কল যোগ হবে —
বাকি predict/Grad-CAM লজিক অপরিবর্তিত থাকবে।

## নতুন dependency (`requirements.txt`-এ যোগ হবে)
```
sqlalchemy
psycopg2-binary
bcrypt
plotly
pytest
python-dotenv
```

## পরবর্তী ধাপ
এই ডিজাইন অনুযায়ী ডিটেইলড implementation plan লেখা হয়ে গেছে:
[docs/superpowers/plans/2026-07-11-admin-dashboard.md](docs/superpowers/plans/2026-07-11-admin-dashboard.md)
(১১টা bite-sized task, প্রতিটাতে TDD স্টেপ/কোড/টেস্ট কমান্ড সহ — ভিজ্যুয়াল ডিজাইন
টোকেন/থিমসহ, দেখুন [docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md](docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md))।
