import random
import json
from datetime import datetime, timedelta
from shapely.geometry import Point, Polygon

# Farm boundary coordinates from your GeoJSON
coords = [
      (130.83916495, -12.46017243),
      (130.83941962, -12.46041745),
      (130.83957579, -12.46026002),
      (130.83932478, -12.46001226),
      (130.83916495, -12.46017243)
  ]

# Create Shapely polygon
polygon = Polygon(coords)
minx, miny, maxx, maxy = polygon.bounds

# Sample pests and diseases for mango cultivation
pests = ['Mango Scale Insect', 'Mango Tip Borer', 'Mango Leaf Hopper', 'Mango Fruit Fly', 'Mango Seed Weevil']
diseases = ['Stem End Rot', 'Mango Malformation', 'Bacterial Black Spot', 'Powdery Mildew', 'Anthracnose']

# Generate random points with pest/disease data
def generate_observation_data(polygon, num_points):
      start_time = datetime.now() - timedelta(hours=3)  # Start 3 hours ago
      observations = []

      # Create a 'hotspot' in a smaller area
      hotspot_center = Point(
          minx + (maxx - minx) * 0.7,  # Hotspot near right side
          miny + (maxy - miny) * 0.3   # Hotspot near top
      )

      # Define infestation probability based on distance from hotspot
      def infestation_probability(point):
          dist = Point(point).distance(hotspot_center)
          # Normalize distance to 0-1 range within polygon dimensions
          max_dist = ((maxx - minx)**2 + (maxy - miny)**2)**0.5
          normalized_dist = dist / max_dist
          # Higher probability closer to hotspot
          return max(0, 1 - (normalized_dist * 3))

      # Generate points
      points_generated = 0
      while points_generated < num_points:
          # Biased sampling: more points near hotspot
          if random.random() < 0.7:  # 70% of points cluster near hotspot
              # Generate point near hotspot with gaussian distribution
              dx = random.gauss(0, (maxx - minx) * 0.15)
              dy = random.gauss(0, (maxy - miny) * 0.15)
              random_point = Point(hotspot_center.x + dx, hotspot_center.y + dy)
          else:
              # Generate truly random point in bounding box
              random_point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))

          # Check if point is inside polygon
          if polygon.contains(random_point):
              # Generate time (sequential)
              obs_time = (start_time + timedelta(minutes=points_generated*3)).strftime('%I:%M %p')

              # Calculate infestation probability based on location
              prob = infestation_probability((random_point.x, random_point.y))

              # Generate pests and diseases with higher probability near hotspot
              obs_pests = []
              obs_diseases = []

              # More pests/diseases near hotspot, fewer further away
              pest_count = random.choices(
                  [0, 1, 2, 3],
                  weights=[1-prob, prob*0.5, prob*0.3, prob*0.2],
                  k=1
              )[0]

              disease_count = random.choices(
                  [0, 1, 2],
                  weights=[1-prob, prob*0.6, prob*0.4],
                  k=1
              )[0]

              if pest_count > 0:
                  obs_pests = random.sample(pests, pest_count)

              if disease_count > 0:
                  obs_diseases = random.sample(diseases, disease_count)

              # 30% chance of having an image, higher near hotspot
              has_image = random.random() < (0.3 + prob * 0.5)

              observations.append({
                  'lat': random_point.y,  # Note: lat is y coordinate
                  'lon': random_point.x,  # lon is x coordinate
                  'time': obs_time,
                  'pests': obs_pests,
                  'diseases': obs_diseases,
                  'has_image': has_image
              })

              points_generated += 1

      return observations

# Generate 20 observations
observation_data = generate_observation_data(polygon, 20)

# Print the data in JSON format for easy copy-paste
print(json.dumps(observation_data, indent=2))