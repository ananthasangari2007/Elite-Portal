import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  Bookmark,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Code2,
  Copy,
  ExternalLink,
  Eye,
  Globe,
  Grid,
  Layers,
  LogOut,
  Maximize2,
  Minimize2,
  Monitor,
  Play,
  RotateCcw,
  Save,
  Send,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  User,
  Video,
  X,
  XCircle,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../../lib/api";
import { useApi, invalidateCache } from "../../lib/hooks";
import { useAuth } from "../../lib/auth";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, Modal, PageLoader, Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

// All 20 compilers from user reference + Web Sandbox
export const ALL_COMPILERS = [
  // Column 1
  { id: "cpp", label: "C++", column: 1, ext: "cpp" },
  { id: "java", label: "Java", column: 1, ext: "java" },
  { id: "python3", label: "Python3", column: 1, ext: "py" },
  { id: "python", label: "Python", column: 1, ext: "py" },
  { id: "javascript", label: "JavaScript", column: 1, ext: "js" },
  { id: "typescript", label: "TypeScript", column: 1, ext: "ts" },
  { id: "csharp", label: "C#", column: 1, ext: "cs" },
  { id: "c", label: "C", column: 1, ext: "c" },

  // Column 2
  { id: "go", label: "Go", column: 2, ext: "go" },
  { id: "kotlin", label: "Kotlin", column: 2, ext: "kt" },
  { id: "swift", label: "Swift", column: 2, ext: "swift" },
  { id: "rust", label: "Rust", column: 2, ext: "rs" },
  { id: "ruby", label: "Ruby", column: 2, ext: "rb" },
  { id: "php", label: "PHP", column: 2, ext: "php" },
  { id: "dart", label: "Dart", column: 2, ext: "dart" },
  { id: "scala", label: "Scala", column: 2, ext: "scala" },

  // Column 3
  { id: "elixir", label: "Elixir", column: 3, ext: "ex" },
  { id: "erlang", label: "Erlang", column: 3, ext: "erl" },
  { id: "racket", label: "Racket", column: 3, ext: "rkt" },
  { id: "web", label: "HTML/CSS/JS (Web)", column: 3, ext: "html" },
];

export const STARTER_TEMPLATES: Record<string, string> = {
  cpp: `#include <iostream>
#include <vector>
#include <string>
using namespace std;

int main() {
    // Write your solution here
    string input;
    if (getline(cin, input)) {
        cout << input << endl;
    }
    return 0;
}
`,
  java: `import java.util.Scanner;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // Write your solution here
        if (sc.hasNextLine()) {
            System.out.println(sc.nextLine());
        }
    }
}
`,
  python3: `import sys

def solve():
    # Write your solution here
    input_data = sys.stdin.read().strip()
    if input_data:
        print(input_data)

if __name__ == "__main__":
    solve()
`,
  python: `import sys

def solve():
    # Write your solution here
    input_data = sys.stdin.read().strip()
    if input_data:
        print(input_data)

if __name__ == "__main__":
    solve()
`,
  javascript: `const fs = require('fs');

function solve() {
    const input = fs.readFileSync(0, 'utf-8').trim();
    // Write your solution here
    if (input) {
        console.log(input);
    }
}

solve();
`,
  typescript: `const fs = require('fs');

function solve(): void {
    const input: string = fs.readFileSync(0, 'utf-8').trim();
    // Write your solution here
    if (input) {
        console.log(input);
    }
}

solve();
`,
  csharp: `using System;

class Program {
    static void Main() {
        // Write your solution here
        string input = Console.ReadLine();
        if (input != null) {
            Console.WriteLine(input);
        }
    }
}
`,
  c: `#include <stdio.h>

int main() {
    // Write your solution here
    char buffer[256];
    if (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        printf("%s", buffer);
    }
    return 0;
}
`,
  go: `package main

import (
    "bufio"
    "fmt"
    "os"
)

func main() {
    // Write your solution here
    scanner := bufio.NewScanner(os.Stdin)
    if scanner.Scan() {
        fmt.Println(scanner.Text())
    }
}
`,
  kotlin: `import java.util.Scanner

fun main() {
    val sc = Scanner(System.\`in\`)
    // Write your solution here
    if (sc.hasNextLine()) {
        println(sc.nextLine())
    }
}
`,
  swift: `import Foundation

// Write your solution here
if let input = readLine() {
    print(input)
}
`,
  rust: `use std::io::{self, Read};

fn main() {
    let mut buffer = String::new();
    let _ = io::stdin().read_to_string(&mut buffer);
    // Write your solution here
    print!("{}", buffer);
}
`,
  ruby: `# Write your solution here
input = ARGF.read
puts input unless input.empty?
`,
  php: `<?php
// Write your solution here
$input = trim(file_get_contents("php://stdin"));
if ($input !== "") {
    echo $input . "\n";
}
`,
  dart: `import 'dart:io';

void main() {
    // Write your solution here
    String? input = stdin.readLineSync();
    if (input != null) {
        print(input);
    }
}
`,
  scala: `import scala.io.StdIn

object Solution {
    def main(args: Array[String]): Unit = {
        // Write your solution here
        val input = StdIn.readLine()
        if (input != null) {
            println(input)
        }
    }
}
`,
  elixir: `defmodule Solution do
  def main do
    # Write your solution here
    input = IO.read(:stdio, :all)
    IO.puts(input)
  end
end

Solution.main()
`,
  erlang: `-module(solution).
-export([start/0]).

start() ->
    % Write your solution here
    ok.
`,
  racket: `#lang racket
;; Write your solution here
(define input (read-line))
(displayln input)
`,
  web: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Solution Preview</title>
  <style>
    body {
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 1.5rem;
      background: #0f172a;
      color: #f8fafc;
    }
    .card {
      border: 1px solid #334155;
      padding: 1rem;
      border-radius: 0.75rem;
      background: #1e293b;
    }
    h2 { color: #38bdf8; margin-top: 0; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Web Sandbox Output</h2>
    <p id="msg">Interactive output will render here.</p>
  </div>
  <script>
    console.log("Web solution loaded successfully.");
  </script>
</body>
</html>
`,
};

export default function TakeAssessment() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { push } = useToast();
  const { data, loading, reload } = useApi<any>(`/attempts/${attemptId}`);

  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [reviewFlags, setReviewFlags] = useState<Record<number, boolean>>({});
  const [visitedQuestions, setVisitedQuestions] = useState<Record<number, boolean>>({});
  const [idx, setIdx] = useState(0);

  // Coding assessment state
  const [code, setCode] = useState<Record<number, string>>({});
  const [language, setLanguage] = useState<Record<number, string>>({});
  const [customInput, setCustomInput] = useState<Record<number, string>>({});
  const [runningCode, setRunningCode] = useState(false);
  const [codeOutput, setCodeOutput] = useState<Record<number, any>>({});
  const [testResults, setTestResults] = useState<Record<number, any>>({});
  const [submittingCode, setSubmittingCode] = useState(false);

  // Layout & Editor UI state
  const [activeOutputTab, setActiveOutputTab] = useState<"result" | "raw" | "custom" | "preview">("result");
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);
  const [paletteDrawerOpen, setPaletteDrawerOpen] = useState(false);
  const [cursorPos, setCursorPos] = useState({ line: 1, col: 1 });

  // Proctoring streams & status
  const [cameraActive, setCameraActive] = useState(false);
  const [screenActive, setScreenActive] = useState(false);
  const [proctoringStarted, setProctoringStarted] = useState(false);
  const [activeFeedTab, setActiveFeedTab] = useState<"camera" | "screen">("camera");

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [warnings, setWarnings] = useState(0);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [showExitModal, setShowExitModal] = useState(false);
  const [fullscreenActive, setFullscreenActive] = useState(true);

  const submittedRef = useRef(false);
  const isPromptingProctorRef = useRef(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const screenVideoRef = useRef<HTMLVideoElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // Filter compilers available for this assessment (from coordinator's allowed_languages)
  const availableCompilers = useMemo(() => {
    const allowed = data?.assessment?.allowed_languages;
    if (Array.isArray(allowed) && allowed.length > 0) {
      return ALL_COMPILERS.filter((c) => allowed.includes(c.id));
    }
    return ALL_COMPILERS;
  }, [data?.assessment?.allowed_languages]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setLangDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Initialize answers and review flags from existing attempt data
  useEffect(() => {
    if (data && !data.finished) {
      const ansMap: Record<number, number> = {};
      const revMap: Record<number, boolean> = {};
      (data.answers || []).forEach((a: any) => {
        if (a.selected_option_id) ansMap[a.question_id] = a.selected_option_id;
        if (a.marked_for_review) revMap[a.question_id] = true;
      });
      setAnswers(ansMap);
      setReviewFlags(revMap);
    }
  }, [data]);

  // Track visited questions as candidate moves
  useEffect(() => {
    if (data?.questions && data.questions[idx]) {
      const currentQId = data.questions[idx].id;
      setVisitedQuestions((prev) => ({ ...prev, [currentQId]: true }));
    }
  }, [idx, data?.questions]);

  // Load results once finished
  useEffect(() => {
    if (data?.finished) {
      api
        .get(`/attempts/${attemptId}/result`)
        .then(setResult)
        .catch((e) => push(e.message, "info"));
    }
  }, [data?.finished, attemptId]);

  // Countdown Timer & Safe Auto-Submit
  useEffect(() => {
    if (!data?.deadline || data.finished) return;
    const deadline = new Date(data.deadline).getTime();
    const tick = () => {
      const diff = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      setRemaining(diff);
      if (diff === 0 && !submittedRef.current) {
        submittedRef.current = true;
        push("Time limit reached. Submitting your assessment automatically...", "warning");
        submit();
      }
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [data?.deadline, data?.finished]);

  // Mandatory Strict Proctoring: Initialize Camera & Single-Prompt Screen Share
  async function startProctoring() {
    if (isPromptingProctorRef.current) return;
    isPromptingProctorRef.current = true;

    // 1. Camera stream (with graceful fallback to avoid OverconstrainedError)
    if (!cameraStreamRef.current || !cameraStreamRef.current.active) {
      try {
        let camStream: MediaStream | null = null;
        try {
          camStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
            audio: false,
          });
        } catch {
          camStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false,
          });
        }
        cameraStreamRef.current = camStream;
        if (videoRef.current) {
          videoRef.current.srcObject = camStream;
        }
        setCameraActive(true);
      } catch (err) {
        console.warn("Camera init:", err);
        setCameraActive(false);
      }
    }

    // 2. Single-Prompt Screen Share (do NOT ask repeatedly if already active)
    if (!screenStreamRef.current || !screenStreamRef.current.active) {
      try {
        if (navigator.mediaDevices && (navigator.mediaDevices as any).getDisplayMedia) {
          const screenStream = await (navigator.mediaDevices as any).getDisplayMedia({
            video: { cursor: "always" },
            audio: false,
          });
          screenStreamRef.current = screenStream;
          if (screenVideoRef.current) {
            screenVideoRef.current.srcObject = screenStream;
          }
          setScreenActive(true);

          const screenTrack = screenStream.getVideoTracks()[0];
          if (screenTrack) {
            screenTrack.onended = () => {
              setScreenActive(false);
            };
          }
        }
      } catch (err) {
        console.warn("Screen share request was cancelled or blocked:", err);
      }
    }

    isPromptingProctorRef.current = false;
    setProctoringStarted(true);
  }

  useEffect(() => {
    if (data?.finished) return;
    startProctoring();

    return () => {
      if (cameraStreamRef.current) {
        cameraStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [data?.finished]);

  // Bind video element refs when streams or feed tabs update
  useEffect(() => {
    if (videoRef.current && cameraStreamRef.current) {
      videoRef.current.srcObject = cameraStreamRef.current;
    }
    if (screenVideoRef.current && screenStreamRef.current) {
      screenVideoRef.current.srcObject = screenStreamRef.current;
    }
  }, [activeFeedTab, cameraActive, screenActive]);

  // Clean Fullscreen management without annoying blur toast warnings
  useEffect(() => {
    if (data?.finished) return;

    function handleFullscreenChange() {
      setFullscreenActive(!!document.fullscreenElement);
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [data?.finished]);

  const questions = data?.questions || [];
  const current = questions[idx];

  // Auto-indentation & Tab handler for code editor
  function handleCodeKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>, questionId: number) {
    const textarea = e.currentTarget;
    const { selectionStart, selectionEnd, value } = textarea;

    // Handle Tab key: insert 4 spaces
    if (e.key === "Tab") {
      e.preventDefault();
      const updated = value.substring(0, selectionStart) + "    " + value.substring(selectionEnd);
      setCode((prev) => ({ ...prev, [questionId]: updated }));
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = selectionStart + 4;
        updateCursor(textarea);
      }, 0);
      return;
    }

    // Handle Enter key: calculate auto-indentation based on language & previous line
    if (e.key === "Enter") {
      e.preventDefault();
      const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
      const currentLine = value.substring(lineStart, selectionStart);
      const match = currentLine.match(/^(\s*)/);
      let indent = match ? match[1] : "";

      const trimmed = currentLine.trim();
      const lang = language[questionId] || availableCompilers[0]?.id || "python";

      // Extra indentation rules for colons or braces
      if (["python", "python3"].includes(lang) && trimmed.endsWith(":")) {
        indent += "    ";
      } else if (["c", "cpp", "java", "javascript", "typescript", "csharp", "rust", "go", "php", "dart", "kotlin", "swift", "scala"].includes(lang) && trimmed.endsWith("{")) {
        indent += "    ";
      }

      const updated = value.substring(0, selectionStart) + "\n" + indent + value.substring(selectionEnd);
      setCode((prev) => ({ ...prev, [questionId]: updated }));
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = selectionStart + 1 + indent.length;
        updateCursor(textarea);
      }, 0);
      return;
    }
  }

  function updateCursor(textarea: HTMLTextAreaElement) {
    const textBefore = textarea.value.substring(0, textarea.selectionStart);
    const lines = textBefore.split("\n");
    setCursorPos({
      line: lines.length,
      col: lines[lines.length - 1].length + 1,
    });
  }

  // Switch programming language
  function handleLanguageChange(questionId: number, newLang: string) {
    setLanguage((prev) => ({ ...prev, [questionId]: newLang }));
    setLangDropdownOpen(false);

    // If code is empty or matches starter of another language, load new starter template
    const currentCode = (code[questionId] || "").trim();
    const isDefault =
      !currentCode ||
      Object.values(STARTER_TEMPLATES).some((t) => t.trim() === currentCode);
    if (isDefault) {
      setCode((prev) => ({ ...prev, [questionId]: STARTER_TEMPLATES[newLang] || "" }));
    }
  }

  // Reset code to default starter template
  function handleResetCode(questionId: number, langId: string) {
    const template = STARTER_TEMPLATES[langId] || "";
    setCode((prev) => ({ ...prev, [questionId]: template }));
    const compilerObj = ALL_COMPILERS.find((c) => c.id === langId);
    push(`Code reset to default ${compilerObj?.label || langId} template.`, "info");
  }

  // Run student code against custom or sample input
  async function runCode(questionId: number) {
    const qLang = language[questionId] || availableCompilers[0]?.id || "python";
    const qCode = code[questionId] !== undefined ? code[questionId] : (STARTER_TEMPLATES[qLang] || "");
    const qInput = customInput[questionId] !== undefined ? customInput[questionId] : (current?.sample_input || "");

    setRunningCode(true);
    setCodeOutput((prev) => ({ ...prev, [questionId]: null }));
    try {
      const res = await api.post<any>(`/attempts/${attemptId}/run-code`, {
        question_id: questionId,
        language: qLang,
        code: qCode,
        custom_input: qInput,
      });
      setCodeOutput((prev) => ({ ...prev, [questionId]: res }));
      setActiveOutputTab("raw");
      if (res.exit_code === 0) {
        push("Code executed successfully.", "success");
      } else {
        push("Execution finished with errors. Inspect output console.", "warning");
      }
    } catch (err: any) {
      setCodeOutput((prev) => ({
        ...prev,
        [questionId]: {
          status: "Error",
          stderr: err.message || "Failed to execute code.",
          exit_code: 1,
        },
      }));
      setActiveOutputTab("raw");
      push(err.message || "Execution failed", "error");
    } finally {
      setRunningCode(false);
    }
  }

  // Submit and grade code with full test cases
  async function submitCode(questionId: number) {
    const qLang = language[questionId] || availableCompilers[0]?.id || "python";
    const qCode = code[questionId] !== undefined ? code[questionId] : (STARTER_TEMPLATES[qLang] || "");

    setSubmittingCode(true);
    try {
      const res = await api.post<any>(`/attempts/${attemptId}/code`, {
        question_id: questionId,
        language: qLang,
        code: qCode,
      });
      setTestResults((prev) => ({ ...prev, [questionId]: res }));
      setActiveOutputTab("result");
      if (res.total_test_cases > 0) {
        push(
          `Evaluated: ${res.passed_count}/${res.total_test_cases} Test Cases Passed (${res.awarded_marks}/${res.max_marks} marks).`,
          res.passed_count === res.total_test_cases ? "success" : "info"
        );
      } else {
        push("Code saved successfully.", "success");
      }
    } catch (err: any) {
      push(err.message || "Failed to submit code.", "error");
    } finally {
      setSubmittingCode(false);
    }
  }

  async function enterFullscreen() {
    try {
      if (document.documentElement.requestFullscreen && !document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        setFullscreenActive(true);
      }
    } catch (_) {}
  }

  async function exitFullscreen() {
    try {
      if (document.exitFullscreen && document.fullscreenElement) {
        await document.exitFullscreen();
        setFullscreenActive(false);
      }
    } catch (_) {}
  }

  async function choose(questionId: number, optionId: number) {
    setAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    try {
      await api.patch(`/attempts/${attemptId}/answers`, {
        question_id: questionId,
        selected_option_id: optionId,
        marked_for_review: !!reviewFlags[questionId],
      });
    } catch (err: any) {
      if (err.code === "time_expired") push("Time is up — please submit.", "error");
    }
  }

  async function clearChoice(questionId: number) {
    setAnswers((prev) => {
      const copy = { ...prev };
      delete copy[questionId];
      return copy;
    });
    try {
      await api.patch(`/attempts/${attemptId}/answers`, {
        question_id: questionId,
        selected_option_id: null,
        marked_for_review: !!reviewFlags[questionId],
      });
    } catch (_) {}
  }

  async function toggleReview(questionId: number) {
    const nextState = !reviewFlags[questionId];
    setReviewFlags((prev) => ({ ...prev, [questionId]: nextState }));
    try {
      await api.patch(`/attempts/${attemptId}/answers`, {
        question_id: questionId,
        selected_option_id: answers[questionId] || null,
        marked_for_review: nextState,
      });
      push(nextState ? "Marked for review" : "Review flag removed", "info");
    } catch (_) {}
  }

  async function markReviewAndNext(questionId: number) {
    if (!reviewFlags[questionId]) {
      await toggleReview(questionId);
    }
    if (idx < questions.length - 1) {
      setIdx((i) => i + 1);
    } else {
      setShowSubmitModal(true);
    }
  }

  function saveAndNext() {
    if (idx < questions.length - 1) {
      setIdx((i) => i + 1);
    } else {
      setShowSubmitModal(true);
    }
  }

  async function submit() {
    if (submitting) return;
    submittedRef.current = true;
    setSubmitting(true);
    setShowSubmitModal(false);
    try {
      const res = await api.post<any>(`/attempts/${attemptId}/submit`);
      push("Assessment submitted successfully.", "success");
      setResult(res.attempt);
      invalidateCache("/student");
      reload();
    } catch (err: any) {
      push(err.message || "Failed to submit assessment.", "error");
      if (remaining != null && remaining > 0) {
        submittedRef.current = false;
      }
    } finally {
      setSubmitting(false);
    }
  }

  function copyText(text: string, label: string) {
    navigator.clipboard.writeText(text);
    push(`Copied ${label} to clipboard.`, "info");
  }

  // Answer statistics
  const answeredCount = Object.keys(answers).length + Object.keys(code).filter((k) => (code[Number(k)] || "").trim().length > 0).length;
  const reviewCount = Object.values(reviewFlags).filter(Boolean).length;
  const unansweredCount = Math.max(0, questions.length - answeredCount);
  const skippedCount = Object.keys(visitedQuestions).filter(
    (qid) => !answers[Number(qid)] && !(code[Number(qid)] && code[Number(qid)].trim().length > 0)
  ).length;
  const notVisitedCount = Math.max(0, questions.length - Object.keys(visitedQuestions).length);

  if (loading) return <PageLoader />;

  // ── Finished / Results View ──────────────────────────────────────────────
  if (data?.finished) {
    const attempt = result || data;
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-12 text-slate-100 flex items-center justify-center font-sans">
        <div className="w-full max-w-xl rounded-3xl bg-slate-900/90 p-8 text-center shadow-2xl border border-slate-800">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-lg">
            <CheckCircle2 className="h-10 w-10" />
          </div>
          <h2 className="mt-6 text-2xl font-bold tracking-tight text-white">Assessment Completed</h2>
          <p className="mt-2 text-sm text-slate-400">
            {data.assessment?.title || "Assessment"} · Completed on {formatDateTime(attempt?.submitted_at || new Date().toISOString())}
          </p>

          <div className="mt-8 grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-slate-800/80 p-4 border border-slate-700/60 text-center">
              <p className="text-2xl font-bold text-white">{attempt?.score ?? "Pending"}</p>
              <p className="text-xs text-slate-400 mt-1 uppercase font-semibold">Your Score</p>
            </div>
            <div className="rounded-xl bg-slate-800/80 p-4 border border-slate-700/60 text-center">
              <p className="text-2xl font-bold text-white">{attempt?.total_marks ?? "—"}</p>
              <p className="text-xs text-slate-400 mt-1 uppercase font-semibold">Total Marks</p>
            </div>
            <div className="rounded-xl bg-slate-800/80 p-4 border border-slate-700/60 text-center">
              <p className="text-2xl font-bold text-emerald-400 capitalize">{humanize(attempt?.status || "graded")}</p>
              <p className="text-xs text-slate-400 mt-1 uppercase font-semibold">Status</p>
            </div>
          </div>

          {attempt?.assessment_type === "betting" && (
            <div className="mt-6 rounded-xl bg-violet-950/60 p-4 text-left text-sm border border-violet-800/50">
              <p className="font-semibold text-violet-200">Betting Points Settled</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <span className="text-violet-400">Locked Points:</span>{" "}
                  <strong className="text-white">{attempt.locked_points}</strong>
                </div>
                <div>
                  <span className="text-violet-400">Attendance:</span>{" "}
                  <strong className="text-white">+{attempt.attendance_points}</strong>
                </div>
                <div>
                  <span className="text-violet-400">Net Awarded:</span>{" "}
                  <strong className="text-emerald-400">{attempt.total_points_awarded} pts</strong>
                </div>
              </div>
            </div>
          )}

          {attempt?.feedback && (
            <div className="mt-6 rounded-xl bg-slate-800/50 p-4 text-left text-sm border border-slate-700/60">
              <p className="text-xs font-semibold uppercase text-slate-400">Evaluator Feedback</p>
              <p className="mt-1 text-slate-300">{attempt.feedback}</p>
            </div>
          )}

          <div className="mt-8">
            <Link
              to="/student/assessments"
              className="inline-flex w-full items-center justify-center rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-lg hover:bg-brand-500 transition"
            >
              Return to Assessments Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const timeLow = remaining != null && remaining <= 300; // <= 5 minutes
  const currentLang = (current && language[current.id]) || availableCompilers[0]?.id || "python";
  const currentCompilerObj = ALL_COMPILERS.find((c) => c.id === currentLang) || ALL_COMPILERS[0];
  const currentQCode = current ? (code[current.id] !== undefined ? code[current.id] : STARTER_TEMPLATES[currentLang] || "") : "";
  const currentOutput = current ? codeOutput[current.id] : null;
  const currentTestRes = current ? testResults[current.id] : null;
  const isCodingQuestion = current?.question_type === "coding";

  // Calculate line numbers for the code editor
  const codeLinesCount = Math.max(16, (currentQCode.match(/\n/g) || []).length + 1);

  // Group available compilers by columns for the LeetCode-style dropdown (Image 5)
  const col1Compilers = availableCompilers.filter((c) => c.column === 1);
  const col2Compilers = availableCompilers.filter((c) => c.column === 2);
  const col3Compilers = availableCompilers.filter((c) => c.column === 3);

  return (
    <div
      onCopy={(e) => {
        if ((e.target as HTMLElement)?.tagName !== "TEXTAREA") {
          e.preventDefault();
          push("Copying is disabled during proctored assessments.", "warning");
        }
      }}
      onContextMenu={(e) => e.preventDefault()}
      className="fixed inset-0 z-50 flex flex-col bg-[#0f1117] text-slate-100 select-none overflow-hidden font-sans"
    >
      {/* ── Top Exam Header ────────────────────────────────────────────── */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-[#161922] px-4 lg:px-6 shadow-md z-30">
        {/* Left: Branding & Assessment Title */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-xs shadow">
            FX
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-xs sm:text-sm font-bold text-white truncate max-w-xs sm:max-w-md">
                {data.assessment?.title || "Elite Assessment"}
              </h1>
              <span className="hidden sm:inline-block rounded bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-300 border border-slate-700">
                {humanize(data.assessment?.assessment_type)}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 truncate">Francis Xavier Engineering College · Elite Batch 2025–2029</p>
          </div>
        </div>

        {/* Center: Proctoring Status & Countdown Timer */}
        <div className="flex items-center gap-2 sm:gap-4">
          <div
            className={clsx(
              "hidden md:flex items-center gap-2 rounded-lg px-2.5 py-1 text-xs font-semibold border",
              !cameraActive || !screenActive
                ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                : "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
            )}
          >
            <span
              className={clsx(
                "h-2 w-2 rounded-full",
                !cameraActive || !screenActive ? "bg-amber-400" : "bg-emerald-400 animate-pulse"
              )}
            />
            <span className="text-[11px]">
              {!cameraActive && !screenActive
                ? "Proctor Standby"
                : !screenActive
                ? "Screen Off"
                : !cameraActive
                ? "Camera Off"
                : "Strict Invigilator Active"}
            </span>
          </div>

          {remaining != null && (
            <div
              className={clsx(
                "flex items-center gap-1.5 rounded-lg px-3 py-1 font-mono text-xs sm:text-sm font-bold tracking-wider border shadow-sm",
                timeLow
                  ? "bg-red-500/20 text-red-300 border-red-500/50 animate-pulse"
                  : "bg-slate-800/90 text-slate-100 border-slate-700"
              )}
            >
              <Clock className={clsx("h-3.5 w-3.5", timeLow ? "text-red-400" : "text-brand-400")} />
              <span>
                {Math.floor((remaining || 0) / 60)}:{String((remaining || 0) % 60).padStart(2, "0")}
              </span>
            </div>
          )}
        </div>

        {/* Right: Actions, Palette Drawer Toggle, Fullscreen & Submit */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Question Palette Drawer Toggle */}
          <button
            onClick={() => setPaletteDrawerOpen(!paletteDrawerOpen)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 border border-slate-700 transition"
            title="Toggle Question Palette & Invigilator"
          >
            <Grid className="h-3.5 w-3.5 text-brand-400" />
            <span className="hidden sm:inline">Palette ({idx + 1}/{questions.length})</span>
          </button>

          <button
            onClick={fullscreenActive ? exitFullscreen : enterFullscreen}
            title={fullscreenActive ? "Exit Fullscreen" : "Enter Fullscreen"}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700 transition"
          >
            {fullscreenActive ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>

          <button
            onClick={() => setShowExitModal(true)}
            className="hidden sm:inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition"
          >
            <LogOut className="h-3.5 w-3.5" /> Exit
          </button>

          <button
            onClick={() => setShowSubmitModal(true)}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-md hover:bg-emerald-500 transition disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-3.5 w-3.5 text-white" /> : <><Send className="h-3.5 w-3.5" /> Submit</>}
          </button>
        </div>
      </header>

      {/* ── Main Workspace Body ────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* If Coding Question: Render Dual-Pane LeetCode Interface (Images 2, 3, 4) */}
        {isCodingQuestion ? (
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
            {/* ── Left Pane: Problem Statement, Constraints, Sample Input/Output (Images 2, 3) ── */}
            <div className="w-full lg:w-[45%] flex flex-col bg-[#11141c] border-r border-slate-800 overflow-hidden">
              {/* Problem Subheader Bar */}
              <div className="flex h-11 shrink-0 items-center justify-between border-b border-slate-800 bg-[#161922] px-4">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-brand-500/10 text-brand-400 px-2 py-0.5 text-xs font-bold uppercase tracking-wider border border-brand-500/20">
                    Task {idx + 1} of {questions.length}
                  </span>
                  <span className="text-slate-600">|</span>
                  <span className="text-xs font-semibold text-slate-300">
                    +{current?.marks || 1} Mark{current?.marks > 1 ? "s" : ""}
                  </span>
                </div>

                <button
                  onClick={() => toggleReview(current.id)}
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold border transition",
                    reviewFlags[current.id]
                      ? "border-violet-500 bg-violet-600/20 text-violet-300"
                      : "border-slate-700 bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white"
                  )}
                >
                  <Bookmark className={clsx("h-3 w-3", reviewFlags[current.id] ? "fill-violet-400 text-violet-400" : "")} />
                  <span>{reviewFlags[current.id] ? "Marked" : "Review"}</span>
                </button>
              </div>

              {/* Problem Statement Content (Scrollable) */}
              <div className="flex-1 overflow-y-auto p-5 space-y-6">
                {/* Problem Statement Header matching Image 3 style */}
                <div>
                  <h2 className="text-base font-bold text-[#f87171] tracking-tight mb-2">
                    Problem Statement
                  </h2>
                  <div className="text-xs sm:text-sm font-normal text-slate-200 leading-relaxed whitespace-pre-wrap">
                    {current.question_text}
                  </div>
                </div>

                {/* Constraints */}
                {current.constraints && (
                  <div className="rounded-xl bg-[#161a24] p-4 border border-slate-800">
                    <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-1.5">
                      Constraints
                    </h3>
                    <p className="text-xs text-slate-300 font-mono whitespace-pre-wrap">
                      {current.constraints}
                    </p>
                  </div>
                )}

                {/* Sample Input and Output matching Image 3 style */}
                {(current.sample_input || current.sample_output) && (
                  <div className="space-y-4">
                    <h2 className="text-base font-bold text-[#f87171] tracking-tight">
                      Sample Input and Output
                    </h2>

                    {current.sample_input && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                          <span>INPUT 1</span>
                          <button
                            onClick={() => copyText(current.sample_input, "Sample Input")}
                            className="inline-flex items-center gap-1 text-[10px] text-brand-400 hover:text-brand-300"
                          >
                            <Copy className="h-3 w-3" /> Copy
                          </button>
                        </div>
                        <div className="rounded-xl bg-[#181d28] p-3 border border-slate-800/90 font-mono text-xs text-slate-200 whitespace-pre-wrap">
                          {current.sample_input}
                        </div>
                      </div>
                    )}

                    {current.sample_output && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                          <span>OUTPUT 1</span>
                          <button
                            onClick={() => copyText(current.sample_output, "Sample Output")}
                            className="inline-flex items-center gap-1 text-[10px] text-brand-400 hover:text-brand-300"
                          >
                            <Copy className="h-3 w-3" /> Copy
                          </button>
                        </div>
                        <div className="rounded-xl bg-[#181d28] p-3 border border-slate-800/90 font-mono text-xs text-emerald-300 whitespace-pre-wrap">
                          {current.sample_output}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Problem Left Pane Navigation Footer */}
              <div className="flex h-12 shrink-0 items-center justify-between border-t border-slate-800 bg-[#161922] px-4">
                <button
                  onClick={() => setIdx((i) => Math.max(0, i - 1))}
                  disabled={idx === 0}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" /> Previous
                </button>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => markReviewAndNext(current.id)}
                    className="rounded-lg border border-violet-700/60 bg-violet-950/40 px-3 py-1.5 text-xs font-semibold text-violet-300 hover:bg-violet-900/50 transition"
                  >
                    Mark & Next
                  </button>

                  <button
                    onClick={saveAndNext}
                    className="inline-flex items-center gap-1 rounded-lg bg-brand-600 px-3.5 py-1.5 text-xs font-bold text-white shadow hover:bg-brand-500 transition"
                  >
                    {idx === questions.length - 1 ? (
                      <>Review <Send className="h-3 w-3" /></>
                    ) : (
                      <>Next <ChevronRight className="h-3 w-3" /></>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* ── Right Pane: Code Area, Editor, Compilers & Output Tabs (Images 3, 4, 5) ── */}
            <div className="w-full lg:w-[55%] flex flex-col bg-[#0f1117] overflow-hidden">
              {/* Code Area Header Bar with Language Picker & Reset (Images 3, 5) */}
              <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-[#161922] px-4 gap-2">
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-[#f87171]" />
                  <span className="text-sm font-bold text-[#f87171]">Code Area</span>
                </div>

                <div className="flex items-center gap-2 relative" ref={dropdownRef}>
                  {/* Reset Code Button matching Image 3 style */}
                  <button
                    onClick={() => handleResetCode(current.id, currentLang)}
                    className="rounded-lg border border-[#f87171]/70 px-3 py-1 text-xs font-semibold text-[#f87171] hover:bg-[#f87171]/10 transition flex items-center gap-1.5"
                    title="Reset to starter template"
                  >
                    <RotateCcw className="h-3 w-3" />
                    <span>Reset your {currentCompilerObj?.label || "Code"}</span>
                  </button>

                  {/* Language Selector Dropdown matching Image 3 & Image 5 */}
                  <button
                    type="button"
                    onClick={() => setLangDropdownOpen(!langDropdownOpen)}
                    className="rounded-lg bg-[#f87171] px-3 py-1 text-xs font-bold text-white shadow hover:bg-[#ef4444] transition flex items-center gap-1.5"
                  >
                    <span>Language: {currentCompilerObj?.label || "Select"}</span>
                    <ChevronDown className="h-3.5 w-3.5 text-white/90" />
                  </button>

                  {/* 3-Column Compiler Dropdown Modal matching Image 5 */}
                  {langDropdownOpen && (
                    <div className="absolute right-0 top-11 z-50 w-[420px] rounded-2xl bg-[#1e222d] border border-slate-700 shadow-2xl p-3 grid grid-cols-3 gap-2">
                      {/* Column 1 */}
                      <div className="space-y-0.5 border-r border-slate-800 pr-2">
                        {col1Compilers.map((c) => {
                          const isSelected = currentLang === c.id;
                          return (
                            <button
                              key={c.id}
                              onClick={() => handleLanguageChange(current.id, c.id)}
                              className={clsx(
                                "w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition",
                                isSelected
                                  ? "bg-brand-600 text-white font-bold"
                                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
                              )}
                            >
                              <span>{c.label}</span>
                              {isSelected && <Check className="h-3.5 w-3.5 text-white shrink-0" />}
                            </button>
                          );
                        })}
                      </div>

                      {/* Column 2 */}
                      <div className="space-y-0.5 border-r border-slate-800 pr-2">
                        {col2Compilers.map((c) => {
                          const isSelected = currentLang === c.id;
                          return (
                            <button
                              key={c.id}
                              onClick={() => handleLanguageChange(current.id, c.id)}
                              className={clsx(
                                "w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition",
                                isSelected
                                  ? "bg-brand-600 text-white font-bold"
                                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
                              )}
                            >
                              <span>{c.label}</span>
                              {isSelected && <Check className="h-3.5 w-3.5 text-white shrink-0" />}
                            </button>
                          );
                        })}
                      </div>

                      {/* Column 3 */}
                      <div className="space-y-0.5">
                        {col3Compilers.map((c) => {
                          const isSelected = currentLang === c.id;
                          return (
                            <button
                              key={c.id}
                              onClick={() => handleLanguageChange(current.id, c.id)}
                              className={clsx(
                                "w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition",
                                isSelected
                                  ? "bg-brand-600 text-white font-bold"
                                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
                              )}
                            >
                              <span className="truncate">{c.label}</span>
                              {isSelected && <Check className="h-3.5 w-3.5 text-white shrink-0" />}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Code Editor with Line Numbers Gutter */}
              <div className="flex-1 flex flex-col min-h-[280px] bg-[#161821] overflow-hidden">
                <div className="flex-1 flex overflow-hidden">
                  {/* Line Number Gutter */}
                  <div className="bg-[#12141c] text-slate-500 select-none py-3 px-3 text-right border-r border-slate-800/80 shrink-0 font-mono text-xs leading-6 overflow-hidden">
                    {Array.from({ length: codeLinesCount }, (_, i) => (
                      <div key={i + 1}>{i + 1}</div>
                    ))}
                  </div>

                  {/* Code Editor Textarea */}
                  <div className="flex-1 relative overflow-auto">
                    <textarea
                      ref={textareaRef}
                      className="w-full h-full min-h-full bg-transparent text-slate-100 p-3 font-mono text-xs leading-6 focus:outline-none resize-none selection:bg-brand-600/40"
                      value={currentQCode}
                      onChange={(e) => {
                        setCode((prev) => ({ ...prev, [current.id]: e.target.value }));
                        updateCursor(e.target);
                      }}
                      onClick={(e) => updateCursor(e.currentTarget)}
                      onKeyUp={(e) => updateCursor(e.currentTarget)}
                      onKeyDown={(e) => handleCodeKeyDown(e, current.id)}
                      spellCheck={false}
                      placeholder={`// Write your ${currentCompilerObj?.label || "code"} solution here`}
                    />
                  </div>
                </div>

                {/* Editor Status Bar matching LeetCode / Image 2 */}
                <div className="flex h-7 shrink-0 items-center justify-between border-t border-slate-800 bg-[#12141c] px-4 text-[11px] text-slate-400 font-mono">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    <span>Saved</span>
                    <span className="text-slate-600">·</span>
                    <span className="text-slate-500">Auto-indent on Enter</span>
                  </div>
                  <div>
                    Ln {cursorPos.line}, Col {cursorPos.col}
                  </div>
                </div>
              </div>

              {/* ── Run Action Button Bar matching Image 4 ── */}
              <div className="border-t border-b border-slate-800 bg-[#161922] p-2.5 px-4 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => runCode(current.id)}
                  disabled={runningCode}
                  className="flex-1 rounded-lg border border-[#f87171] bg-[#f87171]/10 hover:bg-[#f87171]/20 text-[#f87171] py-2 text-xs font-bold transition flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {runningCode ? <Spinner className="h-3.5 w-3.5 text-[#f87171]" /> : <Play className="h-3.5 w-3.5 fill-[#f87171]" />}
                  <span>Run</span>
                </button>

                <button
                  type="button"
                  onClick={() => submitCode(current.id)}
                  disabled={submittingCode}
                  className="rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 text-xs font-bold shadow transition flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {submittingCode ? <Spinner className="h-3.5 w-3.5 text-white" /> : <Save className="h-3.5 w-3.5" />}
                  <span>Submit Solution</span>
                </button>
              </div>

              {/* ── Results and Output Panel matching Image 4 ── */}
              <div className="h-64 sm:h-72 flex flex-col bg-[#11141c] overflow-hidden">
                {/* Title & Tabs Header */}
                <div className="border-b border-slate-800 bg-[#161922] px-4 pt-2.5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#f87171] mb-2">
                    Results and Output
                  </h3>

                  {/* Tabs: RESULT | RAW OUTPUT | CUSTOM TESTCASE | LIVE PREVIEW */}
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <button
                      type="button"
                      onClick={() => setActiveOutputTab("result")}
                      className={clsx(
                        "pb-2 font-bold uppercase transition border-b-2",
                        activeOutputTab === "result"
                          ? "border-[#f87171] text-[#f87171]"
                          : "border-transparent text-slate-400 hover:text-slate-200"
                      )}
                    >
                      RESULT
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveOutputTab("raw")}
                      className={clsx(
                        "pb-2 font-bold uppercase transition border-b-2",
                        activeOutputTab === "raw"
                          ? "border-[#f87171] text-[#f87171]"
                          : "border-transparent text-slate-400 hover:text-slate-200"
                      )}
                    >
                      RAW OUTPUT
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveOutputTab("custom")}
                      className={clsx(
                        "pb-2 font-bold uppercase transition border-b-2",
                        activeOutputTab === "custom"
                          ? "border-[#f87171] text-[#f87171]"
                          : "border-transparent text-slate-400 hover:text-slate-200"
                      )}
                    >
                      CUSTOM TESTCASE
                    </button>

                    {currentLang === "web" && (
                      <button
                        type="button"
                        onClick={() => setActiveOutputTab("preview")}
                        className={clsx(
                          "pb-2 font-bold uppercase transition border-b-2",
                          activeOutputTab === "preview"
                            ? "border-[#f87171] text-[#f87171]"
                            : "border-transparent text-slate-400 hover:text-slate-200"
                        )}
                      >
                        LIVE PREVIEW
                      </button>
                    )}
                  </div>
                </div>

                {/* Tab Contents */}
                <div className="flex-1 overflow-y-auto p-4 font-mono text-xs">
                  {/* Tab 1: RESULT */}
                  {activeOutputTab === "result" && (
                    <div>
                      {!currentTestRes && !currentOutput ? (
                        <div className="h-32 flex items-center justify-center text-slate-400 text-xs">
                          {/* Exact text matching Image 4 */}
                          Please RUN the code to check it against our Testcases.
                        </div>
                      ) : currentTestRes ? (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                            <span className="font-bold text-slate-200 uppercase">
                              Evaluation Verdict
                            </span>
                            <Badge tone={currentTestRes.passed_count === currentTestRes.total_test_cases ? "green" : "amber"}>
                              {currentTestRes.passed_count} / {currentTestRes.total_test_cases} Passed ({currentTestRes.awarded_marks} Marks)
                            </Badge>
                          </div>

                          <div className="space-y-2">
                            {currentTestRes.test_cases?.map((tc: any, i: number) => (
                              <div
                                key={i}
                                className={clsx(
                                  "rounded-lg p-2.5 border text-xs flex items-center justify-between",
                                  tc.passed
                                    ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-300"
                                    : "bg-red-950/20 border-red-900/40 text-red-300"
                                )}
                              >
                                <div className="flex items-center gap-2">
                                  {tc.passed ? (
                                    <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                                  ) : (
                                    <XCircle className="h-4 w-4 text-red-400 shrink-0" />
                                  )}
                                  <span className="font-semibold">
                                    Test Case #{i + 1} {tc.is_hidden ? "(Hidden)" : "(Public)"}
                                  </span>
                                </div>
                                <span className="font-mono text-[11px]">
                                  {tc.passed ? `PASSED (${(tc.execution_time || 0).toFixed(2)}s)` : "FAILED"}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <p className="text-slate-400">
                            Single run finished. To test against all grading test cases, click{" "}
                            <strong className="text-emerald-400">Submit Solution</strong>.
                          </p>
                          <p className="text-slate-500">
                            Status: {currentOutput?.status} (Exit Code {currentOutput?.exit_code})
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 2: RAW OUTPUT */}
                  {activeOutputTab === "raw" && (
                    <div>
                      {currentOutput ? (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-[11px]">
                            <div className="flex items-center gap-2">
                              <span
                                className={clsx(
                                  "h-2 w-2 rounded-full",
                                  currentOutput.exit_code === 0 ? "bg-emerald-400" : "bg-red-400"
                                )}
                              />
                              <span className="font-bold text-slate-300">
                                {currentOutput.status || (currentOutput.exit_code === 0 ? "Success" : "Runtime Error")}
                              </span>
                            </div>
                            <span className="text-slate-500">
                              Exit: {currentOutput.exit_code} · {currentOutput.execution_time_ms || 0}ms
                            </span>
                          </div>

                          {currentOutput.stdout && (
                            <div className="space-y-1">
                              <p className="text-[10px] uppercase font-bold text-slate-500">stdout</p>
                              <pre className="text-emerald-300 bg-[#0d0f14] p-3 rounded-lg border border-slate-800/80 whitespace-pre-wrap">
                                {currentOutput.stdout}
                              </pre>
                            </div>
                          )}

                          {currentOutput.stderr && (
                            <div className="space-y-1">
                              <p className="text-[10px] uppercase font-bold text-red-400">stderr</p>
                              <pre className="text-red-300 bg-red-950/30 p-3 rounded-lg border border-red-900/40 whitespace-pre-wrap">
                                {currentOutput.stderr}
                              </pre>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="h-32 flex items-center justify-center text-slate-500 text-xs">
                          No execution output yet. Click "Run" to test your program.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 3: CUSTOM TESTCASE */}
                  {activeOutputTab === "custom" && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                          Standard Input (stdin)
                        </span>
                        {current?.sample_input && (
                          <button
                            type="button"
                            onClick={() => setCustomInput((prev) => ({ ...prev, [current.id]: current.sample_input }))}
                            className="text-[11px] text-[#f87171] hover:underline"
                          >
                            Reset to Sample Input
                          </button>
                        )}
                      </div>
                      <textarea
                        rows={3}
                        className="w-full rounded-lg bg-[#0d0f14] p-3 font-mono text-xs text-slate-200 border border-slate-800 focus:outline-none focus:border-slate-700 resize-none"
                        placeholder="Type custom test input here..."
                        value={customInput[current.id] !== undefined ? customInput[current.id] : (current.sample_input || "")}
                        onChange={(e) => setCustomInput((prev) => ({ ...prev, [current.id]: e.target.value }))}
                      />
                      <button
                        type="button"
                        onClick={() => runCode(current.id)}
                        disabled={runningCode}
                        className="rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-1.5 text-xs font-semibold text-slate-200 transition"
                      >
                        Run with Custom Input
                      </button>
                    </div>
                  )}

                  {/* Tab 4: LIVE PREVIEW (for Web Sandbox) */}
                  {activeOutputTab === "preview" && currentLang === "web" && (
                    <div className="h-full rounded-xl overflow-hidden border border-slate-800 bg-white">
                      <iframe
                        title="Web Preview Sandbox"
                        srcDoc={currentQCode}
                        className="w-full h-full border-0"
                        sandbox="allow-scripts"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ── Non-Coding MCQ Assessment Layout ── */
          <main className="flex-1 flex flex-col bg-[#11141c] overflow-hidden">
            {/* Question Subheader */}
            <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-[#161922] px-6">
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
                  Question {idx + 1} of {questions.length}
                </span>
                <span className="text-slate-600">|</span>
                <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-semibold text-slate-300">
                  +{current?.marks || 1} Mark{current?.marks > 1 ? "s" : ""}
                </span>
                <span className="text-xs text-slate-500">Multiple Choice</span>
              </div>

              {current && (
                <button
                  onClick={() => toggleReview(current.id)}
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold border transition",
                    reviewFlags[current.id]
                      ? "border-violet-500 bg-violet-600/20 text-violet-300"
                      : "border-slate-700 bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white"
                  )}
                >
                  <Bookmark className={clsx("h-3.5 w-3.5", reviewFlags[current.id] ? "fill-violet-400 text-violet-400" : "")} />
                  <span>{reviewFlags[current.id] ? "Marked for Review" : "Mark for Review"}</span>
                </button>
              )}
            </div>

            {/* Question Card & Radio Options */}
            <div className="flex-1 overflow-y-auto p-6 lg:p-10 space-y-6">
              {current ? (
                <div className="max-w-3xl mx-auto space-y-6">
                  <div className="rounded-2xl bg-[#161922] p-6 border border-slate-800 shadow-sm">
                    <p className="whitespace-pre-wrap text-base font-medium leading-relaxed text-slate-100">
                      {current.question_text}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Choose Option:</p>
                    {current.options?.map((o: any, i: number) => {
                      const selected = answers[current.id] === o.id;
                      const letter = String.fromCharCode(65 + i);
                      return (
                        <button
                          key={o.id}
                          onClick={() => choose(current.id, o.id)}
                          className={clsx(
                            "flex w-full items-center gap-4 rounded-xl border p-4 text-left transition duration-150 group shadow-sm",
                            selected
                              ? "border-brand-500 bg-brand-950/40 text-white ring-1 ring-brand-500/50"
                              : "border-slate-800 bg-[#161922] hover:border-slate-700 hover:bg-slate-800/60 text-slate-200"
                          )}
                        >
                          <span
                            className={clsx(
                              "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold transition",
                              selected
                                ? "bg-brand-600 text-white shadow-md shadow-brand-600/30"
                                : "bg-slate-800 text-slate-400 group-hover:bg-slate-700 group-hover:text-slate-200"
                            )}
                          >
                            {letter}
                          </span>
                          <span className="flex-1 text-sm font-normal leading-relaxed">{o.option_text}</span>
                          <div
                            className={clsx(
                              "h-5 w-5 rounded-full border flex items-center justify-center shrink-0 transition",
                              selected ? "border-brand-500 bg-brand-500 text-white" : "border-slate-700 bg-slate-900"
                            )}
                          >
                            {selected && <div className="h-2 w-2 rounded-full bg-white" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="flex h-64 items-center justify-center text-slate-500">
                  <p>No questions found in this assessment.</p>
                </div>
              )}
            </div>

            {/* MCQ Bottom Footer */}
            <footer className="flex h-16 shrink-0 items-center justify-between border-t border-slate-800 bg-[#161922] px-6">
              <div className="flex items-center gap-3">
                {current && answers[current.id] && (
                  <button
                    onClick={() => clearChoice(current.id)}
                    className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition"
                  >
                    Clear Response
                  </button>
                )}
                {current && (
                  <button
                    onClick={() => markReviewAndNext(current.id)}
                    className="rounded-xl border border-violet-700/60 bg-violet-950/40 px-3.5 py-2 text-xs font-semibold text-violet-300 hover:bg-violet-900/50 transition"
                  >
                    Mark for Review & Next
                  </button>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIdx((i) => Math.max(0, i - 1))}
                  disabled={idx === 0}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </button>

                <button
                  onClick={saveAndNext}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-5 py-2 text-xs font-bold text-white shadow-lg hover:bg-brand-500 transition"
                >
                  {idx === questions.length - 1 ? (
                    <>Review & Submit <Send className="h-3.5 w-3.5" /></>
                  ) : (
                    <>Save & Next <ChevronRight className="h-4 w-4" /></>
                  )}
                </button>
              </div>
            </footer>
          </main>
        )}

        {/* ── Slide-Out Question Palette & Proctoring Invigilator Drawer ── */}
        {paletteDrawerOpen && (
          <aside className="absolute top-0 right-0 bottom-0 w-80 sm:w-96 bg-[#161922] border-l border-slate-800 shadow-2xl z-40 flex flex-col">
            {/* Drawer Header */}
            <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 px-4 bg-[#12141c]">
              <div className="flex items-center gap-2 text-xs font-bold text-white uppercase tracking-wider">
                <ShieldAlert className="h-4 w-4 text-emerald-400" />
                <span>Invigilation & Palette</span>
              </div>
              <button
                onClick={() => setPaletteDrawerOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Video Streams Panel */}
            <div className="p-4 border-b border-slate-800 bg-[#0f1117]/60 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400">
                <span className="text-[11px]">Proctor Video Feed</span>
                <div className="flex items-center gap-1 rounded bg-slate-800 p-0.5 border border-slate-700 text-[10px]">
                  <button
                    type="button"
                    onClick={() => setActiveFeedTab("camera")}
                    className={clsx(
                      "px-2 py-0.5 rounded font-semibold transition",
                      activeFeedTab === "camera" ? "bg-brand-600 text-white" : "text-slate-400 hover:text-white"
                    )}
                  >
                    Camera
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveFeedTab("screen")}
                    className={clsx(
                      "px-2 py-0.5 rounded font-semibold transition",
                      activeFeedTab === "screen" ? "bg-brand-600 text-white" : "text-slate-400 hover:text-white"
                    )}
                  >
                    Screen
                  </button>
                </div>
              </div>

              <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black border border-slate-800 flex items-center justify-center shadow-inner">
                {/* Camera Video Stream */}
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={clsx(
                    "h-full w-full object-cover",
                    activeFeedTab === "camera" ? "block" : "hidden"
                  )}
                />

                {/* Screen Share Video Stream */}
                <video
                  ref={screenVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className={clsx(
                    "h-full w-full object-cover",
                    activeFeedTab === "screen" ? "block" : "hidden"
                  )}
                />

                {/* Live indicators */}
                <div className="absolute top-2 left-2 flex items-center gap-1.5 rounded bg-black/80 px-2 py-0.5 text-[10px] font-bold text-red-400 border border-red-500/20 backdrop-blur-sm">
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                  <span>{activeFeedTab === "camera" ? "CAM LIVE" : "SCREEN LIVE"}</span>
                </div>

                {!cameraActive && activeFeedTab === "camera" && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/90 text-slate-400 text-xs gap-1">
                    <Video className="h-6 w-6 text-red-400" />
                    <span>Camera Standby</span>
                  </div>
                )}

                {!screenActive && activeFeedTab === "screen" && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/90 text-slate-400 text-xs gap-1">
                    <Monitor className="h-6 w-6 text-amber-400" />
                    <span>Screen Share Inactive</span>
                    <button
                      onClick={startProctoring}
                      className="mt-1 px-2.5 py-1 bg-brand-600 text-white rounded text-[11px] font-semibold"
                    >
                      Enable Screen Share
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Status Legend */}
            <div className="p-3 border-b border-slate-800 bg-[#12141c] text-xs">
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  <span className="text-slate-300">Answered ({answeredCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-violet-500" />
                  <span className="text-slate-300">Review ({reviewCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                  <span className="text-slate-300">Skipped ({skippedCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-600" />
                  <span className="text-slate-300">Unvisited ({notVisitedCount})</span>
                </div>
              </div>
            </div>

            {/* Question Palette Grid */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                All Questions ({questions.length})
              </p>
              <div className="grid grid-cols-5 gap-2">
                {questions.map((q: any, i: number) => {
                  const isCurrent = i === idx;
                  const isAnswered = !!answers[q.id] || !!code[q.id];
                  const isMarked = !!reviewFlags[q.id];
                  const isVisited = !!visitedQuestions[q.id];

                  let bgClass = "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700 hover:text-white";
                  if (isMarked && isAnswered) {
                    bgClass = "bg-violet-600 text-white font-bold border border-violet-400";
                  } else if (isMarked) {
                    bgClass = "bg-violet-600/80 text-violet-100 font-bold border border-violet-500";
                  } else if (isAnswered) {
                    bgClass = "bg-emerald-600 text-white font-bold border border-emerald-500";
                  } else if (isVisited) {
                    bgClass = "bg-rose-500/20 text-rose-300 border border-rose-500/40";
                  }

                  return (
                    <button
                      key={q.id}
                      onClick={() => {
                        setIdx(i);
                        setPaletteDrawerOpen(false);
                      }}
                      className={clsx(
                        "flex h-9 items-center justify-center rounded-lg text-xs font-bold transition cursor-pointer",
                        bgClass,
                        isCurrent && "ring-2 ring-brand-400 scale-105"
                      )}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* ── Submission Confirmation Modal ───────────────────────────────── */}
      <Modal
        open={showSubmitModal}
        onClose={() => setShowSubmitModal(false)}
        title="Final Test Submission"
        subtitle="Review your attempt statistics before final submission."
        footer={
          <>
            <button
              className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
              onClick={() => setShowSubmitModal(false)}
            >
              Return to Questions
            </button>
            <button
              className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-500 transition shadow"
              disabled={submitting}
              onClick={submit}
            >
              {submitting ? <Spinner className="h-4 w-4 text-white" /> : "Confirm and Submit Exam"}
            </button>
          </>
        }
      >
        <div className="space-y-4 text-sm text-slate-600">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-emerald-50 p-3.5 border border-emerald-100">
              <p className="text-2xl font-bold text-emerald-700">{answeredCount}</p>
              <p className="text-xs font-semibold text-emerald-600 mt-1 uppercase">Answered</p>
            </div>
            <div className="rounded-xl bg-violet-50 p-3.5 border border-violet-100">
              <p className="text-2xl font-bold text-violet-700">{reviewCount}</p>
              <p className="text-xs font-semibold text-violet-600 mt-1 uppercase">Marked Review</p>
            </div>
            <div className="rounded-xl bg-rose-50 p-3.5 border border-rose-100">
              <p className="text-2xl font-bold text-rose-700">{unansweredCount}</p>
              <p className="text-xs font-semibold text-rose-600 mt-1 uppercase">Unanswered</p>
            </div>
          </div>

          {unansweredCount > 0 && (
            <div className="rounded-xl bg-amber-50 p-3.5 border border-amber-200 text-xs text-amber-900 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
              <span>
                Attention: You still have <strong>{unansweredCount} unanswered question(s)</strong>.
              </span>
            </div>
          )}

          <p className="text-xs text-slate-500">
            Once submitted, your responses will be evaluated and your score will be settled.
          </p>
        </div>
      </Modal>

      {/* ── Exit Confirmation Modal ─────────────────────────────────────── */}
      <Modal
        open={showExitModal}
        onClose={() => setShowExitModal(false)}
        title="Leave Assessment Window?"
        subtitle="Your answers are saved, but the timer will continue running."
        footer={
          <>
            <button
              className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
              onClick={() => setShowExitModal(false)}
            >
              Stay in Exam
            </button>
            <button
              className="rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-500 transition"
              onClick={() => navigate("/student/assessments")}
            >
              Exit to Dashboard
            </button>
          </>
        }
      >
        <div className="text-sm text-slate-600 space-y-2">
          <p>
            Are you sure you want to exit the examination window? If your scheduled assessment window closes while you are away, your attempt will expire.
          </p>
        </div>
      </Modal>
    </div>
  );
}
