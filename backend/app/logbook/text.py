"""Text people type. PostgreSQL text cannot hold NUL, so it is refused here rather than failing
in the database."""

from typing import Annotated

from pydantic import StringConstraints

NO_NUL = r"^[^\x00]*$"

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=NO_NUL)]
