import datetime

def determine_stage_and_p():
    """
    Determines the current farming stage and expected prevalence (p) 
    based on the current month according to the defined mapping.
    
    Returns:
        tuple: (stage_name: str, prevalence_p: float)
    """
    month = datetime.datetime.now().month
    
    # Mapping based on approach.md pseudocode logic
    if 6 <= month <= 8: # June - August
        return "Flowering", 0.05
    elif 9 <= month <= 12: # September - December
        return "Fruit Development", 0.07
    elif 1 <= month <= 4: # January - April 
        return "Wet Season", 0.10
    elif month == 5: # May
        return "Dry Season", 0.02
    else:
        # Fallback or default case if month logic is somehow missed
        # Reverting to Wet season prevalence as it's highest risk generally
        print(f"Warning: Could not determine stage for month {month}. Defaulting to Wet Season.")
        return "Wet Season", 0.10 

def get_active_threats_and_parts(stage):
    """
    Returns lists of active pest names, disease names, and plant part names
    based on the provided farming stage.
    
    Args:
        stage (str): The current farming stage (e.g., "Flowering").
        
    Returns:
        dict: {
            "pest_names": list[str], 
            "disease_names": list[str], 
            "part_names": list[str]
        }
    """
    pest_disease_mapping = {
        "Flowering": {
            "pests": ["Mango Leaf Hopper", "Mango Tip Borer"],
            "diseases": ["Powdery Mildew", "Mango Malformation"]
        },
        "Fruit Development": {
            "pests": ["Mango Fruit Fly", "Mango Seed Weevil", "Mango Scale Insect"],
            "diseases": ["Anthracnose", "Bacterial Black Spot", "Stem End Rot"]
        },
        "Wet Season": {
            # Combined from approach.md notes
            "pests": ["Mango Fruit Fly", "Mango Seed Weevil", "Mango Tip Borer", "Mango Scale Insect"], 
            "diseases": ["Anthracnose", "Bacterial Black Spot"]
        },
        "Dry Season": {
            "pests": ["Mango Leaf Hopper", "Mango Tip Borer", "Mango Scale Insect"],
            "diseases": ["Powdery Mildew", "Mango Malformation"]
        }
    }
    
    plant_part_mapping = {
        "Flowering": ["Flowers", "Leaves", "Branches"],
        "Fruit Development": ["Fruits", "Leaves", "Branches"],
        # Assuming 'Wet Season' from mapping means peak rain focus
        "Wet Season": ["Fruits", "Leaves", "Stems"], 
        # Assuming 'Dry Season' from mapping means non-flowering focus
        "Dry Season": ["Stems", "Branches"] 
    }

    # Get data for the current stage, default to empty lists if stage not found
    threats = pest_disease_mapping.get(stage, {"pests": [], "diseases": []})
    parts = plant_part_mapping.get(stage, [])
    
    return {
        "pest_names": threats["pests"],
        "disease_names": threats["diseases"],
        "part_names": parts
    } 