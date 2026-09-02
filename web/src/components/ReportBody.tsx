type Props = {
  text: string;
};

export function ReportBody({ text }: Props) {
  const blocks = text.split("\n");
  return (
    <div className="report">
      {blocks.map((line, index) => {
        if (line.startsWith("# ")) {
          return <h1 key={index}>{line.slice(2)}</h1>;
        }
        if (line.startsWith("## ")) {
          return <h2 key={index}>{line.slice(3)}</h2>;
        }
        if (line.trim() === "") {
          return <div key={index} className="gap" />;
        }
        return <p key={index}>{line}</p>;
      })}
    </div>
  );
}
