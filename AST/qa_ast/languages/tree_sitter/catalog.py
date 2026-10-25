"""Tree-sitter parser catalog for the languages recognized by QA Train."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TreeSitterSpec:
    language_id: str
    display_name: str
    grammar_by_extension: dict[str, str]
    grammar_by_filename: dict[str, str] = field(default_factory=dict)
    filename_prefixes: tuple[tuple[str, str], ...] = ()

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset(self.grammar_by_extension)

    def grammar_for(self, path: Path) -> str | None:
        name = Path(path).name.casefold()
        if name in self.grammar_by_filename:
            return self.grammar_by_filename[name]
        for prefix, grammar in self.filename_prefixes:
            if name == prefix or name.startswith(prefix + "."):
                return grammar
        return self.grammar_by_extension.get(Path(path).suffix.lower())


SPECS = (
    TreeSitterSpec("javascript", "JavaScript", {".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript"}),
    TreeSitterSpec("typescript", "TypeScript", {".ts": "typescript", ".tsx": "tsx"}),
    TreeSitterSpec("vue", "Vue", {".vue": "vue"}),
    TreeSitterSpec("svelte", "Svelte", {".svelte": "svelte"}),
    TreeSitterSpec("astro", "Astro", {".astro": "astro"}),
    TreeSitterSpec("html", "HTML", {".html": "html", ".htm": "html"}),
    TreeSitterSpec("css", "CSS", {".css": "css", ".scss": "scss", ".sass": "scss", ".less": "css"}),
    TreeSitterSpec("java", "Java", {".java": "java", ".jsp": "java"}),
    TreeSitterSpec("kotlin", "Kotlin", {".kt": "kotlin", ".kts": "kotlin"}),
    TreeSitterSpec("scala", "Scala", {".scala": "scala"}),
    TreeSitterSpec("groovy", "Groovy", {".groovy": "groovy", ".gradle": "groovy"}),
    TreeSitterSpec("csharp", "C#", {".cs": "csharp", ".csx": "csharp"}),
    TreeSitterSpec("razor", "Razor", {".cshtml": "razor", ".razor": "razor"}),
    TreeSitterSpec("fsharp", "F#", {".fs": "fsharp", ".fsx": "fsharp", ".fsi": "fsharp_signature"}),
    TreeSitterSpec("vbnet", "Visual Basic .NET", {".vb": "vb"}),
    TreeSitterSpec("c", "C", {".c": "c", ".h": "c"}),
    TreeSitterSpec("cpp", "C++", {".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp"}),
    TreeSitterSpec("objective_c", "Objective-C", {".m": "objc", ".mm": "objc"}),
    TreeSitterSpec("matlab", "MATLAB/Octave", {".m": "matlab"}),
    TreeSitterSpec("swift", "Swift", {".swift": "swift"}),
    TreeSitterSpec("rust", "Rust", {".rs": "rust"}),
    TreeSitterSpec("go", "Go", {".go": "go"}),
    TreeSitterSpec("dart", "Dart", {".dart": "dart"}),
    TreeSitterSpec("sql", "SQL", {".sql": "sql"}),
    TreeSitterSpec("r", "R", {".r": "r"}),
    TreeSitterSpec("julia", "Julia", {".jl": "julia"}),
    TreeSitterSpec("ruby", "Ruby", {".rb": "ruby"}, {"rakefile": "ruby", "gemfile": "ruby", "podfile": "ruby", "fastfile": "ruby"}),
    TreeSitterSpec("php", "PHP", {".php": "php", ".phtml": "php"}),
    TreeSitterSpec("perl", "Perl", {".pl": "perl", ".pm": "perl"}),
    TreeSitterSpec("lua", "Lua", {".lua": "lua"}),
    TreeSitterSpec("terraform", "Terraform/HCL", {".tf": "terraform", ".tfvars": "terraform", ".hcl": "hcl"}),
    TreeSitterSpec("bicep", "Bicep", {".bicep": "bicep"}),
    TreeSitterSpec("rego", "Rego", {".rego": "rego"}),
    TreeSitterSpec("dockerfile", "Dockerfile", {}, filename_prefixes=(("dockerfile", "dockerfile"), ("containerfile", "dockerfile"))),
    TreeSitterSpec("make", "Make", {}, {"makefile": "make", "gnumakefile": "make"}),
    TreeSitterSpec("cmake", "CMake", {}, {"cmakelists.txt": "cmake"}),
    TreeSitterSpec("elixir", "Elixir", {".ex": "elixir", ".exs": "elixir"}),
    TreeSitterSpec("erlang", "Erlang", {".erl": "erlang", ".hrl": "erlang"}),
    TreeSitterSpec("clojure", "Clojure", {".clj": "clojure", ".cljs": "clojure", ".cljc": "clojure"}),
    TreeSitterSpec("haskell", "Haskell", {".hs": "haskell", ".lhs": "haskell"}),
    TreeSitterSpec("ocaml", "OCaml", {".ml": "ocaml", ".mli": "ocaml_interface"}),
    TreeSitterSpec("solidity", "Solidity", {".sol": "solidity"}),
    TreeSitterSpec("graphql", "GraphQL", {".graphql": "graphql", ".gql": "graphql"}),
    TreeSitterSpec("protobuf", "Protocol Buffers", {".proto": "proto"}),
    TreeSitterSpec("powershell", "PowerShell", {".ps1": "powershell", ".psm1": "powershell", ".psd1": "powershell"}),
    TreeSitterSpec("shell", "Shell", {".sh": "bash", ".bash": "bash", ".zsh": "bash"}, {".bashrc": "bash", ".bash_profile": "bash", ".zshrc": "bash", ".profile": "bash"}),
    TreeSitterSpec("fish", "Fish shell", {".fish": "fish"}),
    TreeSitterSpec("gdscript", "GDScript", {".gd": "gdscript"}),
    TreeSitterSpec("elm", "Elm", {".elm": "elm"}),
    TreeSitterSpec("zig", "Zig", {".zig": "zig"}),
    TreeSitterSpec("nim", "Nim", {".nim": "nim"}),
    TreeSitterSpec("assembly", "Assembly", {".asm": "asm", ".s": "asm"}),
    TreeSitterSpec("verilog", "Verilog", {".v": "verilog"}),
    TreeSitterSpec("systemverilog", "SystemVerilog", {".sv": "systemverilog"}),
    TreeSitterSpec("vhdl", "VHDL", {".vhd": "vhdl", ".vhdl": "vhdl"}),
)


SPECS_BY_ID = {spec.language_id: spec for spec in SPECS}
