import type { Metadata } from "next";
import Link from "next/link";
import PublicPageShell from "@/components/common/public-page-shell";

export const metadata: Metadata = {
  title: "License | gPawa",
  description: "Software license and intellectual property notice for gPawa.",
};

export default function LicensePage() {
  return (
    <PublicPageShell
      title="License & intellectual property"
      subtitle="Software rights and permitted use of gPawa materials."
    >
      <h2>Software</h2>
      <p>
        The gPawa web application, mobile application, APIs, documentation, branding, and related materials are
        proprietary to the gPawa project and its licensors unless otherwise stated in writing.
      </p>

      <h2>Your licence to use the service</h2>
      <p>
        When you register for gPawa, we grant you a personal, non-exclusive, non-transferable licence to access and
        use the platform for lawful household or institutional energy management in accordance with our{" "}
        <Link href="/terms">Terms of Service</Link>. You may not copy, reverse-engineer, scrape, or resell access to
        the platform.
      </p>

      <h2>Trademarks</h2>
      <p>
        &ldquo;gPawa&rdquo;, the gPawa logo, and related marks are trademarks of the project. You may not use them
        without prior written permission except to refer to the service factually.
      </p>

      <h2>Open-source components</h2>
      <p>
        gPawa may include open-source libraries subject to their own licences (for example MIT, Apache 2.0, BSD).
        Source code for those components is available from their respective publishers. Nothing on this page limits
        your rights under those third-party licences.
      </p>

      <h2>Research and pilot use</h2>
      <p>
        Academic and research partners participating in approved pilot programmes may receive additional licence
        terms under separate agreements. Contact us for partnership licensing.
      </p>

      <h2>Enquiries</h2>
      <p>
        Licensing and IP questions: <Link href="/contact">contact page</Link> or{" "}
        <a href="mailto:gpawateam@gmail.com">gpawateam@gmail.com</a>.
      </p>
    </PublicPageShell>
  );
}
