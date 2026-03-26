"use client";

import Hero from "@/features/home/Hero";
import About from "@/features/home/About";
import Activities from "@/features/home/Activities";
import Projects from "@/features/home/Projects";
import Members from "@/features/home/Members";

export default function LandingPage() {
  return (
    <div className="w-full pb-12">
      <Hero />
      <About />
      <Activities />
      <Projects />
      <Members />
    </div>
  );
}