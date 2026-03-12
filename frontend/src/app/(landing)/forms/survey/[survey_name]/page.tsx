import { notFound } from "next/navigation";
import SurveyForm from "@/components/form/SurveyForm";

interface PageProps {
  params: {
    survey_name: string;
  };
}

export default async function DynamicSurveyPage({ params }: PageProps) {
  let formData = null;

  try {
    formData = (await import(`@/data/forms/${params.survey_name}.json`)).default;
  } catch {
    notFound();
  }

  return <SurveyForm formData={formData} />;
}