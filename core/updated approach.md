# Project Report: Mango Farm Surveillance - Dynamic Pest, Disease, and Sampling Logic Implementation

## 1. Introduction
The goal of the mango surveillance application is to help growers in Northern Australia dynamically:
- Calculate the minimum number of plants they must survey (sample size) for pest and disease monitoring.
- Display high-priority pests and diseases depending on the current farming stage (flowering, fruiting, wet season, dry season).
- Advise growers which parts of the plant to inspect based on the active threats.
This ensures a professional, scientific, and user-friendly experience without needing manual selection of seasons by the grower.

## 2. Season and Stage Mapping
Northern Australia experiences:
- Dry Season: May – October
- Wet Season: November – April

Inside Dry Season:
- Flowering Period: June – August
- Fruit Development Period: September – December (extends slightly into early wet)

## 3. Active Pest and Disease Mapping

| Stage/Season | Active Pests | Active Diseases |
|--------------|--------------|-----------------|
| Flowering (June–August) | Mango Leaf Hopper, Mango Tip Borer | Powdery Mildew, Mango Malformation |
| Fruit Development (September–December) | Mango Fruit Fly, Mango Seed Weevil, Mango Scale Insect | Anthracnose, Bacterial Black Spot, Stem End Rot |
| Wet Season (November–April) | Mango Fruit Fly, Mango Seed Weevil (early wet), Mango Tip Borer (late wet), Mango Scale Insect | Anthracnose, Bacterial Black Spot |
| Dry Season (May–October) | Mango Leaf Hopper, Mango Tip Borer, Mango Scale Insect | Powdery Mildew, Mango Malformation |

## 4. Plant Parts Surveillance Focus

| Stage/Season | Plant Parts to Inspect |
|--------------|------------------------|
| Flowering | Flowers, Leaves, Branches |
| Fruit Development | Fruits, Leaves, Branches |
| Wet Season (Peak Rain) | Fruits, Leaves, Stems |
| Dry Season (Non-flowering) | Stems, Branches |

Special Note: Mango Seed Weevil affects Seeds, but surveillance is done by checking Fruits externally.

## 5. Sampling (Sample Size) Calculation Logic
Formula:
For finite population:

n = m / (1 + ((m - 1) / N))

Where:
- N = Total number of plants (user input)
- z = z-score based on confidence level selected by user
- p = Expected prevalence (risk) based on current season/stage
- d = Margin of error (fixed at 5% = 0.05)
- m = (z² * p * (1-p)) / d²

p (Expected Prevalence) Mapping:

| Stage/Season | Expected Prevalence (p) |
|--------------|-------------------------|
| Flowering (June–August) | 5% (0.05) |
| Fruit Development (September–December) | 7% (0.07) |
| Wet Season (November–April) | 10% (0.10) |
| Dry Season (May–October) | 2% (0.02) |

## 6. Pseudocode for Dynamic Implementation

```python
import datetime
import math

def determine_stage_and_p():
    month = datetime.datetime.now().month
    if month in [6, 7, 8]:
        return "Flowering", 0.05
    elif month in [9, 10]:
        return "Fruit Development", 0.07
    elif month in [11, 12, 1, 2, 3, 4]:
        return "Wet Season", 0.10
    else:
        return "Dry Season", 0.02

def get_active_pests_diseases(stage):
    mapping = {
        "Flowering": {
            "pests": ["Mango Leaf Hopper", "Mango Tip Borer"],
            "diseases": ["Powdery Mildew", "Mango Malformation"]
        },
        "Fruit Development": {
            "pests": ["Mango Fruit Fly", "Mango Seed Weevil", "Mango Scale Insect"],
            "diseases": ["Anthracnose", "Bacterial Black Spot", "Stem End Rot"]
        },
        "Wet Season": {
            "pests": ["Mango Fruit Fly", "Mango Seed Weevil", "Mango Tip Borer", "Mango Scale Insect"],
            "diseases": ["Anthracnose", "Bacterial Black Spot"]
        },
        "Dry Season": {
            "pests": ["Mango Leaf Hopper", "Mango Tip Borer", "Mango Scale Insect"],
            "diseases": ["Powdery Mildew", "Mango Malformation"]
        }
    }
    return mapping[stage]

def calculate_sample_size(N, confidence_level, p):
    z_scores = {"90%": 1.645, "95%": 1.960, "99%": 2.575}
    z = z_scores[confidence_level]
    d = 0.05  # fixed margin of error

    m = (z**2 * p * (1-p)) / (d**2)
    n = m / (1 + ((m - 1) / N))
    return min(N, math.ceil(n))  # sample size cannot exceed total plants
```

## 7. Display Logic in the Frontend
On the farm detail page:
- Auto-detect stage based on current system month.
- Display:
  - Current Stage (e.g., "Flowering Period")
  - Priority Pests (list from active pests)
  - Priority Diseases (list from active diseases)
  - Plant Parts to Inspect (depending on active pests/diseases)
- Auto-calculate sample size and display the required number of plants to inspect based on user's total plants and selected confidence level.

## 8. Conclusion
This approach ensures the surveillance system:
- Requires minimal user input (only number of plants and desired confidence).
- Dynamically adapts to time of year and stage of mango growth.
- Focuses the grower's efforts on real, seasonally relevant threats.
- Remains simple enough for quick loading, low maintenance, and strong usability.

This logical structure builds a robust, real-world ready mango surveillance web application for Northern Australia.
