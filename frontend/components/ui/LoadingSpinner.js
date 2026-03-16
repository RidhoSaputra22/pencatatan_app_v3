export default function LoadingSpinner({ text = "Loading..." }) {
  return (
    <div className="flex flex-col items-center justify-center py-10">
      <span className="loading loading-spinner loading-lg text-success" />
      <p className="mt-3 text-sm opacity-70">{text}</p>
    </div>
  );
}
