import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata = {
  title: "Visitor Monitoring",
  description: "Monitoring jumlah pengunjung perpustakaan",
  icons: {},
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
