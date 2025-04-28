import datetime

def determine_stage_and_p(override_month=None):
    """
    Determines the farming stage and expected prevalence (p) 
    based on the provided month (or current month if not provided).
    
    Args:
        override_month (int, optional): A month number (1-12) to use 
                                        instead of the current system month. 
                                        Defaults to None.

    Returns:
        tuple: (stage_name: str, prevalence_p: float, month_used: int)
    """
    month_to_use = None
    if override_month is not None:
        try:
            month_val = int(override_month)
            if 1 <= month_val <= 12:
                month_to_use = month_val
                print(f"DEBUG: Using overridden month: {month_to_use}") # Debug print
            else:
                print(f"Warning: Invalid override_month ({override_month}). Using current month.")
        except (ValueError, TypeError):
            print(f"Warning: Could not parse override_month ({override_month}). Using current month.")

    # If override wasn't valid or provided, use current system month
    if month_to_use is None:
        month_to_use = datetime.datetime.now().month
        # print(f"DEBUG: Using current system month: {month_to_use}") # Optional debug

    # Mapping based on approach.md pseudocode logic
    if 6 <= month_to_use <= 8: # June - August
        stage, p = "Flowering", 0.05
    elif 9 <= month_to_use <= 12: # September - December
        stage, p = "Fruit Development", 0.07
    elif 1 <= month_to_use <= 4: # January - April 
        stage, p = "Wet Season", 0.10
    elif month_to_use == 5: # May
        stage, p = "Dry Season", 0.02
    else:
        # Fallback or default case if month logic is somehow missed (shouldn't happen with validation)
        print(f"Warning: Could not determine stage for month {month_to_use}. Defaulting to Wet Season.")
        stage, p = "Wet Season", 0.10 
        
    return stage, p, month_to_use # Return the month actually used

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