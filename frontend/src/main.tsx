import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import "./styles.css";

const api = axios.create({ baseURL: `${import.meta.env.VITE_API_URL}/api` });

type TrendPoint = { date: string; label: string; productivity_score: number };
type WeeklyStats = { completions: number; focus_minutes: number; productivity_score: number; trend: TrendPoint[] };

function App() {
  const { loginWithRedirect, logout, isAuthenticated, getAccessTokenSilently, user } = useAuth0();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const request = async (path: string) => {
    api.defaults.headers.Authorization = `Bearer ${await getAccessTokenSilently()}`;
    return api.get(path).then((response) => response.data);
  };
  const habits = useQuery({ queryKey: ["habits"], queryFn: () => request("/habits"), enabled: isAuthenticated });
  const stats = useQuery<WeeklyStats>({ queryKey: ["stats"], queryFn: () => request("/analytics/weekly"), enabled: isAuthenticated });
  const add = useMutation({
    mutationFn: async () => {
      api.defaults.headers.Authorization = `Bearer ${await getAccessTokenSilently()}`;
      return api.post("/habits", { title });
    },
    onSuccess: () => { setTitle(""); queryClient.invalidateQueries({ queryKey: ["habits"] }); },
  });

  if (!isAuthenticated) {
    return <main className="hero"><p className="eyebrow">HABITFLOW</p><h1>Build momentum.<br />Make it visible.</h1><p>Private habits, focused work, and calm analytics in one place.</p><button onClick={() => loginWithRedirect({ appState: { returnTo: "/dashboard" } })}>Continue securely</button></main>;
  }

  return <main className="app">
    <aside><b>HABITFLOW</b><a>Overview</a><a>Habits</a><a>Tasks</a><a>Analytics</a><a>Calendar</a><button onClick={() => logout({ logoutParams: { returnTo: location.origin } })}>Log out</button></aside>
    <section>
      <header><div><p className="eyebrow">GOOD MORNING, {user?.name?.split(" ")[0]?.toUpperCase()}</p><h1>Your intentional day</h1></div><button className="ghost">{new Date().toLocaleDateString()}</button></header>
      <div className="metrics"><Card n={stats.data?.productivity_score ?? "—"} t="Weekly score" /><Card n={stats.data?.focus_minutes ?? 0} t="Focus minutes" /><Card n={stats.data?.completions ?? 0} t="Habit completions" /></div>
      <div className="grid">
        <article><h2>Today’s habits</h2><form onSubmit={(event) => { event.preventDefault(); if (title.trim()) add.mutate(); }}><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Add a habit…" /><button>Add</button></form>{habits.isLoading ? <p>Loading your habits…</p> : habits.data?.length ? habits.data.map((habit: any) => <div className="habit" key={habit.id}><span>○</span><b>{habit.title}</b><small>{habit.frequency} · {habit.category}</small></div>) : <p className="empty">Your first small promise belongs here.</p>}</article>
        <article><h2>Productivity trend</h2><p className="chart-note">Current workweek; calculated from your saved completions and focus sessions.</p><ResponsiveContainer width="100%" height={250}><BarChart data={stats.data?.trend ?? []}><XAxis dataKey="label" /><Tooltip /><Bar dataKey="productivity_score" name="Productivity score" fill="#a3e635" radius={8} /></BarChart></ResponsiveContainer></article>
      </div>
    </section>
  </main>;
}

function Card({ n, t }: { n: string | number; t: string }) {
  return <div className="card"><strong>{n}</strong><span>{t}</span></div>;
}

const queryClient = new QueryClient();
createRoot(document.getElementById("root")!).render(<Auth0Provider domain={import.meta.env.VITE_AUTH_DOMAIN} clientId={import.meta.env.VITE_AUTH_CLIENT_ID} authorizationParams={{ redirect_uri: location.origin, audience: import.meta.env.VITE_AUTH_AUDIENCE }}><QueryClientProvider client={queryClient}><App /></QueryClientProvider></Auth0Provider>);
