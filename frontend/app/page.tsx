import { AskWorkspace } from "@/features/ask/ask-workspace";

const SUGGESTIONS = [
  "What is photosynthesis?",
  "What are Newton's laws of motion?",
  "What is 15% of 240?",
  "Is Pluto a planet?",
  "How many continents are there?",
  "Tell me about Julius Caesar",
];

export default function HomePage() {
  return <AskWorkspace suggestions={SUGGESTIONS} />;
}
