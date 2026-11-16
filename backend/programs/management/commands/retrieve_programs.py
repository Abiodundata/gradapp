from django.core.management.base import BaseCommand, CommandError

from programs.models import GraduateProgram
from programs.retrieval import retrieve_program_information


class Command(BaseCommand):
    help = "Retrieve program information from official websites (Retrieve Program Information use case)."

    def add_arguments(self, parser):
        parser.add_argument("ids", nargs="*", type=int, help="Program IDs. Omit and use --stale or --all.")
        parser.add_argument("--all", action="store_true", help="Retrieve every active program.")
        parser.add_argument("--stale", action="store_true", help="Retrieve only programs with stale or missing information.")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and extract, but do not update programs.")

    def handle(self, *args, **options):
        programs = GraduateProgram.objects.filter(is_active=True).select_related("university")
        if options["ids"]:
            programs = programs.filter(id__in=options["ids"])
        elif not (options["all"] or options["stale"]):
            raise CommandError("Provide program IDs, --stale, or --all.")
        if options["stale"]:
            programs = [program for program in programs if program.is_stale]

        for program in programs:
            snapshot = retrieve_program_information(program, apply=not options["dry_run"])
            style = self.style.SUCCESS if snapshot.status == "success" else self.style.WARNING
            detail = ", ".join(snapshot.applied_fields) or snapshot.error or "no changes"
            self.stdout.write(style(f"[{snapshot.status}] {program}: {detail}"))
