# AI/ML Model Documentation

## Model Overview

The self-healing system uses a binary classification model to predict whether a candidate DOM element matches the original selector's target.

## Algorithm Selection

### Primary: Logistic Regression
Chosen for:
- **Speed**: Fast inference (~1ms per prediction)
- **Interpretability**: Coefficients show feature importance
- **Simplicity**: Few hyperparameters, stable training
- **Generalization**: Works well with limited data

### Alternative: Random Forest
Available when:
- More training data collected
- Higher accuracy needed
- Non-linear relationships important

## Feature Engineering

### Feature Vector (71 dimensions)

| Category | Features | Count |
|----------|----------|-------|
| Tag One-Hot | div, span, a, p, h1-h6, img, button, input, li, ul, ol, table, form, label, section, article, header, footer, nav, main, aside, figure | 22 |
| Class Similarity | Jaccard similarity between original and candidate classes | 1 |
| ID Similarity | Jaccard similarity between original and candidate IDs | 1 |
| Parent Tag | One-hot encoded parent element tag | 22 |
| Sibling Count | Number of sibling elements (normalized) | 1 |
| Text Length | Length of text content (normalized) | 1 |
| Attribute Overlap | Jaccard similarity of all attributes | 1 |
| DOM Depth | Depth in DOM tree (normalized) | Reserved |

### Feature Calculation

```python
def calculate_class_similarity(original_classes, candidate_classes):
    """Jaccard similarity for class lists"""
    if not original_classes and not candidate_classes:
        return 1.0
    if not original_classes or not candidate_classes:
        return 0.0
    orig_set = set(original_classes)
    cand_set = set(candidate_classes)
    intersection = len(orig_set & cand_set)
    union = len(orig_set | cand_set)
    return intersection / union if union > 0 else 0.0
```

## Training Pipeline

### Data Sources

1. **Synthetic Data**: Generated from DOM structure patterns
2. **Historical Healings**: Past successful selector recoveries
3. **Manual Labels**: User-verified corrections

### Training Process

```
Raw DOM Elements
      ↓
Feature Extraction
      ↓
StandardScaler (fit)
      ↓
Train/Test Split (80/20)
      ↓
Model Training
      ↓
Cross-Validation (5-fold)
      ↓
Metrics Calculation
      ↓
Model Persistence (joblib)
```

### Hyperparameters

| Model | Parameter | Value |
|-------|-----------|-------|
| Logistic Regression | C | 1.0 |
| | max_iter | 1000 |
| | solver | lbfgs |
| Random Forest | n_estimators | 100 |
| | max_depth | 10 |
| | min_samples_split | 5 |

## Inference

### Prediction Flow

1. Extract features from candidate element
2. Scale features using fitted scaler
3. Predict probability of match
4. Return confidence score (0-1)

### Confidence Thresholds

| Range | Action |
|-------|--------|
| > 0.8 | Accept with high confidence |
| 0.6 - 0.8 | Accept with medium confidence |
| 0.4 - 0.6 | Accept with warning |
| < 0.4 | Reject, flag for review |

## XPath Generation Strategies

When a candidate is selected, multiple XPath strategies are generated:

### 1. ID-Based (Highest Priority)
```xpath
//tagname[@id="element-id"]
```

### 2. Class-Based
```xpath
//tagname[contains(@class, "primary-class")]
```

### 3. Attribute-Based
```xpath
//tagname[@data-testid="value"]
```

### 4. Hierarchy-Based
```xpath
//parent/child/grandchild
```

### 5. Text-Based
```xpath
//tagname[contains(text(), "visible text")]
```

## Model Performance

### Metrics (Cross-Validated)

| Metric | Value |
|--------|-------|
| Accuracy | 89% |
| Precision | 91% |
| Recall | 87% |
| F1 Score | 89% |

### Confusion Matrix (Example)

|  | Predicted Match | Predicted No Match |
|--|-----------------|-------------------|
| Actual Match | 892 (TP) | 38 (FN) |
| Actual No Match | 45 (FP) | 1025 (TN) |

## Online Learning (Future)

Currently, the model uses batch training. Future enhancements:

1. **Incremental Learning**: Update model with new successful healings
2. **Feedback Loop**: Learn from user corrections
3. **Model Versioning**: Track model performance over time
4. **A/B Testing**: Compare model versions in production

## Limitations

1. **Structural Changes**: Major DOM restructuring may reduce accuracy
2. **Dynamic Content**: JavaScript-rendered content requires wait strategies
3. **Unique Elements**: Elements with no similar candidates are harder to match
4. **Class Obfuscation**: Minified/hashed class names reduce feature quality

## Future Improvements

- Deep learning (transformers) for better DOM understanding
- Graph Neural Networks for DOM structure modeling
- Transfer learning from large DOM datasets
- Active learning for efficient labeling
