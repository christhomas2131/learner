import { AskWorkspace } from "@/features/ask/ask-workspace";

const SUGGESTIONS = [
  "What is photosynthesis?",
  "When was the Roman Republic established?",
  "What is 15% of 240?",
  "What is cellular respiration?",
];

export default function HomePage() {
  return <AskWorkspace suggestions={SUGGESTIONS} />;
}
