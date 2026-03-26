"use client";

import React from 'react';
import { hackathon2025Data } from '@/data/event/datahackathon2025';
import EventHero from "@/features/events/EventHero";
import EventTimeline from "@/features/events/EventTimeline";
import EventDetails from "@/features/events/EventDetails";
import EventRegistration from "@/features/events/EventRegistration";

export default function EventPage() {
  const eventData = hackathon2025Data;

  return (
    <div className="w-full font-sans text-slate-800">
      <EventHero event={eventData} />
      <EventDetails event={eventData} />
      <EventTimeline timelines={eventData.timelines} />
      <EventRegistration event={eventData} />
    </div>
  );
}