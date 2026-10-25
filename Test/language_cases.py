"""Minimal, deterministic sources for every QA Train language adapter.

The marker is replaced with two integer literals to build Ver.A and Ver.B.
Keep fixtures free of network, filesystem, and runtime side effects: parsers
read these files, but the sources are never executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent


VALUE_MARKER = "__QA_VALUE__"


@dataclass(frozen=True)
class LanguageCase:
    language_id: str
    group: str
    filename: str
    source_template: str

    def source(self, value: int) -> str:
        if self.source_template.count(VALUE_MARKER) != 1:
            raise ValueError(f"{self.language_id}: fixture must contain one {VALUE_MARKER}")
        rendered = self.source_template.replace(VALUE_MARKER, str(value))
        return dedent(rendered).strip() + "\n"


def _case(language_id: str, group: str, filename: str, source: str) -> LanguageCase:
    return LanguageCase(language_id, group, filename, source)


CASES = (
    _case("javascript", "web", "app.js", """
        function helper(value) { return value + 1; }
        function entry() { return helper(__QA_VALUE__); }
    """),
    _case("typescript", "web", "app.ts", """
        function helper(value: number): number { return value + 1; }
        export function entry(): number { return helper(__QA_VALUE__); }
    """),
    _case("vue", "web", "App.vue", """
        <script setup lang="ts">
        const qaValue = __QA_VALUE__
        function entry() { return qaValue }
        </script>
        <template><p>{{ entry() }}</p></template>
    """),
    _case("svelte", "web", "App.svelte", """
        <script>
        const qaValue = __QA_VALUE__;
        function entry() { return qaValue; }
        </script>
        <p>{entry()}</p>
    """),
    _case("astro", "web", "Page.astro", """
        ---
        const qaValue = __QA_VALUE__;
        function entry() { return qaValue; }
        ---
        <p>{entry()}</p>
    """),
    _case("html", "web", "index.html", """
        <!doctype html><html><body><main data-qa-value="__QA_VALUE__">QA</main></body></html>
    """),
    _case("css", "web", "styles.css", """
        :root { --qa-value: __QA_VALUE__; }
        .qa { z-index: var(--qa-value); }
    """),

    _case("java", "jvm", "QaSample.java", """
        final class QaSample {
            static int helper(int value) { return value + 1; }
            static int entry() { return helper(__QA_VALUE__); }
        }
    """),
    _case("kotlin", "jvm", "QaSample.kt", """
        fun helper(value: Int): Int = value + 1
        fun entry(): Int = helper(__QA_VALUE__)
    """),
    _case("scala", "jvm", "QaSample.scala", """
        object QaSample {
          def helper(value: Int): Int = value + 1
          def entry(): Int = helper(__QA_VALUE__)
        }
    """),
    _case("groovy", "jvm", "QaSample.groovy", """
        int helper(int value) { value + 1 }
        int entry() { helper(__QA_VALUE__) }
    """),

    _case("csharp", "dotnet", "QaSample.cs", """
        static class QaSample {
            static int Helper(int value) => value + 1;
            public static int Entry() => Helper(__QA_VALUE__);
        }
    """),
    _case("razor", "dotnet", "QaSample.razor", """
        <p>@qaValue</p>
        @code { private int qaValue = __QA_VALUE__; }
    """),
    _case("fsharp", "dotnet", "QaSample.fs", """
        module QaSample
        let helper value = value + 1
        let entry () = helper __QA_VALUE__
    """),
    _case("vbnet", "dotnet", "QaSample.vb", """
        Module QaSample
            Function Entry() As Integer
                Return __QA_VALUE__
            End Function
        End Module
    """),

    _case("c", "native", "qa_sample.c", """
        int helper(int value) { return value + 1; }
        int entry(void) { return helper(__QA_VALUE__); }
    """),
    _case("cpp", "native", "qa_sample.cpp", """
        constexpr int helper(int value) { return value + 1; }
        int entry() { return helper(__QA_VALUE__); }
    """),
    _case("objective_c", "native", "QaSample.m", """
        #import <Foundation/Foundation.h>
        int helper(int value) { return value + 1; }
        int entry(void) { return helper(__QA_VALUE__); }
    """),
    _case("swift", "native", "QaSample.swift", """
        func helper(_ value: Int) -> Int { value + 1 }
        func entry() -> Int { helper(__QA_VALUE__) }
    """),
    _case("rust", "native", "qa_sample.rs", """
        fn helper(value: i32) -> i32 { value + 1 }
        pub fn entry() -> i32 { helper(__QA_VALUE__) }
    """),
    _case("go", "native", "qa_sample.go", """
        package qa
        func helper(value int) int { return value + 1 }
        func entry() int { return helper(__QA_VALUE__) }
    """),
    _case("dart", "native", "qa_sample.dart", """
        int helper(int value) => value + 1;
        int entry() => helper(__QA_VALUE__);
    """),
    _case("zig", "native", "qa_sample.zig", """
        fn helper(value: i32) i32 { return value + 1; }
        pub fn entry() i32 { return helper(__QA_VALUE__); }
    """),
    _case("nim", "native", "qa_sample.nim", """
        proc helper(value: int): int = value + 1
        proc entry(): int = helper(__QA_VALUE__)
    """),
    _case("assembly", "native", "qa_sample.asm", """
        .data
        qa_value: .byte __QA_VALUE__
        .text
        .globl _start
        _start:
          mov $1, %eax
    """),
    _case("verilog", "native", "qa_sample.v", """
        module qa_sample(output wire [7:0] value);
          assign value = __QA_VALUE__;
        endmodule
    """),
    _case("systemverilog", "native", "qa_sample.sv", """
        module qa_sample;
          int value = __QA_VALUE__;
        endmodule
    """),
    _case("vhdl", "native", "qa_sample.vhd", """
        library ieee;
        use ieee.std_logic_1164.all;
        entity qa_sample is end entity qa_sample;
        architecture rtl of qa_sample is
          constant QA_VALUE : integer := __QA_VALUE__;
        begin
        end architecture rtl;
    """),

    _case("python", "data-script", "qa_sample.py", """
        def helper(value: int) -> int:
            return value + 1

        def entry() -> int:
            return helper(__QA_VALUE__)
    """),
    _case("sql", "data-script", "qa_sample.sql", """
        CREATE VIEW qa_view AS SELECT __QA_VALUE__ AS qa_value;
    """),
    _case("r", "data-script", "qa_sample.r", """
        helper <- function(value) value + 1
        entry <- function() helper(__QA_VALUE__)
    """),
    _case("julia", "data-script", "qa_sample.jl", """
        helper(value) = value + 1
        entry() = helper(__QA_VALUE__)
    """),
    _case("matlab", "data-script", "qa_sample.m", """
        function result = entry()
          result = helper(__QA_VALUE__);
        end
        function result = helper(value)
          result = value + 1;
        end
    """),
    _case("ruby", "data-script", "qa_sample.rb", """
        def helper(value) = value + 1
        def entry = helper(__QA_VALUE__)
    """),
    _case("php", "data-script", "qa_sample.php", """
        <?php
        function helper(int $value): int { return $value + 1; }
        function entry(): int { return helper(__QA_VALUE__); }
    """),
    _case("perl", "data-script", "qa_sample.pl", """
        use strict;
        sub helper { my ($value) = @_; return $value + 1; }
        sub entry { return helper(__QA_VALUE__); }
    """),
    _case("lua", "data-script", "qa_sample.lua", """
        local function helper(value) return value + 1 end
        local function entry() return helper(__QA_VALUE__) end
    """),
    _case("powershell", "data-script", "qa_sample.ps1", """
        function Get-QaValue([int]$Value) { return $Value + 1 }
        Get-QaValue -Value __QA_VALUE__
    """),
    _case("shell", "data-script", "qa_sample.sh", """
        helper() { echo "$(($1 + 1))"; }
        entry() { helper __QA_VALUE__; }
        entry
    """),
    _case("fish", "data-script", "qa_sample.fish", """
        function helper
          math $argv[1] + 1
        end
        function entry
          helper __QA_VALUE__
        end
        entry
    """),

    _case("terraform", "infrastructure", "main.tf", """
        locals { qa_value = __QA_VALUE__ }
        output "qa_value" { value = local.qa_value }
    """),
    _case("bicep", "infrastructure", "main.bicep", """
        var qaValue = __QA_VALUE__
        output result int = qaValue
    """),
    _case("rego", "infrastructure", "qa.rego", """
        package qa
        default allow := false
        allow if { input.value == __QA_VALUE__ }
    """),
    _case("dockerfile", "infrastructure", "Dockerfile", """
        FROM scratch
        ARG QA_VALUE=__QA_VALUE__
    """),
    _case("make", "infrastructure", "Makefile", """
        QA_VALUE := __QA_VALUE__
        all:
        \t@echo $(QA_VALUE)
    """),
    _case("cmake", "infrastructure", "CMakeLists.txt", """
        cmake_minimum_required(VERSION 3.20)
        project(QATest)
        set(QA_VALUE __QA_VALUE__)
    """),

    _case("elixir", "other", "qa_sample.ex", """
        defmodule QaSample do
          def helper(value), do: value + 1
          def entry, do: helper(__QA_VALUE__)
        end
    """),
    _case("erlang", "other", "qa_sample.erl", """
        -module(qa_sample).
        -export([entry/0]).
        entry() -> helper(__QA_VALUE__).
        helper(Value) -> Value + 1.
    """),
    _case("clojure", "other", "qa_sample.clj", """
        (ns qa.sample)
        (defn helper [value] (+ value 1))
        (defn entry [] (helper __QA_VALUE__))
    """),
    _case("haskell", "other", "QaSample.hs", """
        module QaSample where
        helper :: Int -> Int
        helper value = value + 1
        entry :: Int
        entry = helper __QA_VALUE__
    """),
    _case("ocaml", "other", "qa_sample.ml", """
        let helper value = value + 1
        let entry () = helper __QA_VALUE__
    """),
    _case("solidity", "other", "QaSample.sol", """
        pragma solidity ^0.8.0;
        contract QaSample {
          function entry() public pure returns (uint256) { return __QA_VALUE__; }
        }
    """),
    _case("graphql", "other", "qa_sample.graphql", """
        type Query { qaValue: Int! }
        query Qa($value: Int = __QA_VALUE__) { qaValue }
    """),
    _case("protobuf", "other", "qa_sample.proto", """
        syntax = "proto3";
        package qa;
        message QaValue { int32 value = __QA_VALUE__; }
    """),
    _case("gdscript", "other", "qa_sample.gd", """
        extends Node
        func helper(value: int) -> int:
            return value + 1
        func entry() -> int:
            return helper(__QA_VALUE__)
    """),
    _case("elm", "other", "QaSample.elm", """
        module QaSample exposing (entry)
        helper value = value + 1
        entry = helper __QA_VALUE__
    """),
)


CASES_BY_ID = {case.language_id: case for case in CASES}
GROUPS = tuple(sorted({case.group for case in CASES}))

if len(CASES_BY_ID) != len(CASES):
    raise RuntimeError("language fixture ids must be unique")
