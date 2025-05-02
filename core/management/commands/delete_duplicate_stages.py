import sys
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction # Import transaction
# Use relative import within the app
from ...models import SeasonalStage

class Command(BaseCommand):
    help = 'Finds and deletes duplicate SeasonalStage entries based on the name field, keeping the one with the lowest ID.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("--- Starting duplicate SeasonalStage cleanup --- "))

        # --- Debug: Print total count ---
        total_count = SeasonalStage.objects.count()
        self.stdout.write(f"Total SeasonalStage records found: {total_count}")
        if total_count == 0:
             self.stdout.write(self.style.SUCCESS("No SeasonalStage records exist. Exiting."))
             return # Exit handle method normally
             
        # --- Debug: Show counts for all names ---
        name_counts_all = (
            SeasonalStage.objects.values('name')
            .annotate(name_count=Count('id'))
            .order_by('name') # Order for readability
        )
        self.stdout.write("Counts per stage name:")
        for item in name_counts_all:
            self.stdout.write(f"  - Name: '{item['name']}', Count: {item['name_count']}")
        self.stdout.write("---")
        
        # Find names with more than one entry (QuerySet)
        duplicates_qs = (
            SeasonalStage.objects.values('name')
            .annotate(name_count=Count('id'))
            .filter(name_count__gt=1)
        )
        
        # --- Debug: Print the generated SQL query ---
        try:
            sql_query, params = duplicates_qs.query.sql_with_params()
            self.stdout.write(self.style.SQL_KEYWORD("SQL Query for finding duplicates:"))
            self.stdout.write(sql_query % params) # Simple formatting for display
            self.stdout.write("---")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not get SQL query: {e}"))

        # Get the actual list of names
        duplicate_names_list = list(duplicates_qs.values_list('name', flat=True))

        deleted_count = 0
        if not duplicate_names_list:
            self.stdout.write(self.style.SUCCESS("No duplicate SeasonalStage names found based on query."))
            return # Exit handle method normally

        self.stdout.write(f"Found duplicate names: {duplicate_names_list}")

        # Use a transaction for the deletion part
        try:
            with transaction.atomic():
                for name in duplicate_names_list:
                    self.stdout.write(f"Processing duplicates for: '{name}'")
                    # Get all instances for this name, ordered by ID
                    stages = SeasonalStage.objects.filter(name=name).order_by('id')
                    
                    stage_to_keep = stages.first()
                    if stage_to_keep is None:
                        self.stdout.write(self.style.WARNING(f"  Could not find stage to keep for name '{name}'. Skipping."))
                        continue
                        
                    self.stdout.write(f"  Keeping stage '{name}' with ID: {stage_to_keep.id}")

                    # Identify stages to delete
                    stages_to_delete_qs = stages.exclude(id=stage_to_keep.id)
                    count_for_name = stages_to_delete_qs.count()
                    
                    if count_for_name > 0:
                        deleted_ids = list(stages_to_delete_qs.values_list('id', flat=True))
                        self.stdout.write(f"  Attempting to delete {count_for_name} duplicate(s) with IDs: {deleted_ids}")
                        
                        # Perform the deletion
                        num_deleted, types_deleted = stages_to_delete_qs.delete()
                        self.stdout.write(f"  Deletion result: {num_deleted} objects deleted. Types: {types_deleted}")
                        if num_deleted > 0:
                             deleted_count += num_deleted
                        else:
                             self.stdout.write(self.style.WARNING(f"  Deletion reported 0 objects deleted for '{name}' despite finding {count_for_name} candidates."))
                    else:
                        self.stdout.write(f"  No duplicates found to delete for '{name}' (ID: {stage_to_keep.id} was the only one).")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred during the deletion process: {e}"))
            raise # Re-raise the exception after logging

        self.stdout.write(self.style.SUCCESS(f"--- Cleanup complete. Total duplicates deleted: {deleted_count} ---")) 