import {
  Award,
  BarChart3,
  Bell,
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  FileSearch,
  Gauge,
  GraduationCap,
  Layers,
  LayoutDashboard,
  Library,
  Megaphone,
  MessageSquare,
  Scale,
  ScrollText,
  Settings,
  ShieldCheck,
  Target,
  TrendingUp,
  UserCog,
  Users,
} from "lucide-react";
import type { Role } from "./auth";

export type NavItem = { label: string; to: string; icon: any; end?: boolean };
export type NavSection = { title?: string; items: NavItem[] };

export const NAV: Record<Role, NavSection[]> = {
  student: [
    {
      items: [
        { label: "Dashboard", to: "/student", icon: LayoutDashboard, end: true },
        { label: "Learning Path", to: "/student/learning", icon: BookOpen },
        { label: "Assessments", to: "/student/assessments", icon: ClipboardCheck },
        { label: "Elite Tasks", to: "/student/tasks", icon: Target },
      ],
    },
    {
      title: "My progress",
      items: [
        { label: "My Domains", to: "/student/domains", icon: Layers },
        { label: "Points & Rewards", to: "/student/points", icon: Award },
        { label: "Leaderboard", to: "/student/leaderboard", icon: TrendingUp },
      ],
    },
    {
      title: "Support",
      items: [
        { label: "Requests", to: "/requests", icon: MessageSquare },
        { label: "Notifications", to: "/notifications", icon: Bell },
        { label: "Profile", to: "/profile", icon: UserCog },
      ],
    },
  ],
  coordinator: [
    {
      items: [
        { label: "Dashboard", to: "/coordinator", icon: LayoutDashboard, end: true },
        { label: "Learning Days", to: "/coordinator/content", icon: Library },
        { label: "Assessments", to: "/coordinator/assessments", icon: ClipboardCheck },
        { label: "Submissions", to: "/coordinator/submissions", icon: ClipboardList },
      ],
    },
    {
      title: "Insights",
      items: [
        { label: "Students", to: "/coordinator/students", icon: Users },
        { label: "Analytics", to: "/coordinator/analytics", icon: BarChart3 },
      ],
    },
    {
      title: "Support",
      items: [
        { label: "Requests", to: "/requests", icon: MessageSquare },
        { label: "Notifications", to: "/notifications", icon: Bell },
        { label: "Profile", to: "/profile", icon: UserCog },
      ],
    },
  ],
  faculty: [
    {
      items: [
        { label: "Dashboard", to: "/faculty", icon: LayoutDashboard, end: true },
        { label: "Grading Queue", to: "/faculty/grading", icon: ClipboardCheck },
        { label: "Task Evidence", to: "/faculty/evidence", icon: FileSearch },
        { label: "Appeals", to: "/faculty/appeals", icon: Scale },
        { label: "Point Adjustments", to: "/faculty/adjustments", icon: Gauge },
      ],
    },
    {
      title: "Insights",
      items: [{ label: "Analytics", to: "/faculty/analytics", icon: BarChart3 }],
    },
    {
      title: "Support",
      items: [
        { label: "Requests", to: "/requests", icon: MessageSquare },
        { label: "Notifications", to: "/notifications", icon: Bell },
        { label: "Profile", to: "/profile", icon: UserCog },
      ],
    },
  ],
  admin: [
    {
      items: [
        { label: "Dashboard", to: "/admin", icon: LayoutDashboard, end: true },
        { label: "Users", to: "/admin/users", icon: Users },
        { label: "Domains", to: "/admin/domains", icon: Layers },
        { label: "Content", to: "/admin/content", icon: Library },
        { label: "Assessments", to: "/admin/assessments", icon: ClipboardCheck },
        { label: "Elite Tasks", to: "/admin/tasks", icon: Target },
      ],
    },
    {
      title: "Operations",
      items: [
        { label: "Announcements", to: "/admin/announcements", icon: Megaphone },
        { label: "Settings", to: "/admin/settings", icon: Settings },
        { label: "Audit Logs", to: "/admin/audit", icon: ScrollText },
      ],
    },
    {
      title: "Support",
      items: [
        { label: "Notifications", to: "/notifications", icon: Bell },
        { label: "Profile", to: "/profile", icon: UserCog },
      ],
    },
  ],
};

export const ROLE_META: Record<Role, { label: string; icon: any; color: string; blurb: string }> = {
  student: {
    label: "Student",
    icon: GraduationCap,
    color: "#4f46e5",
    blurb: "Access your learning path, assessments, daily tasks and rewards.",
  },
  coordinator: {
    label: "Domain Coordinator",
    icon: Library,
    color: "#0ea5e9",
    blurb: "Build learning content, manage assessments and grade submissions.",
  },
  faculty: {
    label: "Faculty Coordinator",
    icon: ShieldCheck,
    color: "#7c3aed",
    blurb: "Review evidence, resolve appeals and supervise point adjustments.",
  },
  admin: {
    label: "Admin",
    icon: UserCog,
    color: "#0f766e",
    blurb: "Govern users, domains, content, platform settings and audit trails.",
  },
};
