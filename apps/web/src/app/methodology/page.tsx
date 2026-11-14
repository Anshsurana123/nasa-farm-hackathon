"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n";
import {
  AlertTriangle,
  ArrowLeft,
  FlaskConical,
  Satellite,
  ShieldCheck,
} from "lucide-react";

export default function MethodologyPage() {
  const { t } = useI18n();
  return (
    <AppShell
      pageStep="REF"
      pageBadge={t("methodology.pageBadge")}
      pageTitle={t("methodology.pageTitle")}
      pageDescription={t("methodology.pageDesc")}
      headerActions={
        <Link
          href="/"
          className="px-4 py-2.5 rounded-xl bg-surface-2 hover:bg-surface border border-line text-foreground font-mono text-xs font-bold flex items-center gap-2 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-emerald-400" />
          <span>{t("methodology.returnBtn")}</span>
        </Link>
      }
    >
      <div className="space-y-8">
        {/* 1. NASA Datasets Registry */}
        <section className="glass rounded-2xl border border-line overflow-hidden reticle-frame">
          <div className="instrument-header px-6 py-3.5 flex items-center justify-between">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <Satellite className="w-4 h-4 text-emerald-400" />
              <span>{t("methodology.sec01")}</span>
            </h2>
            <span className="text-[10px] font-mono text-muted">{t("methodology.headerTag")}</span>
          </div>

          <div className="p-6 overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-line text-muted font-mono text-[10px] uppercase tracking-wider">
                  <th className="py-2.5 pr-4">{t("methodology.thDataset")}</th>
                  <th className="py-2.5 pr-4">{t("methodology.thProduct")}</th>
                  <th className="py-2.5 pr-4">{t("methodology.thResolution")}</th>
                  <th className="py-2.5 pr-4">{t("methodology.thRole")}</th>
                  <th className="py-2.5">{t("methodology.thDoi")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line font-mono text-[11px]">
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsPowerName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsPowerProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsPowerRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsPowerRole")}</td>
                  <td className="py-3 text-cyan-400">{"power.larc.nasa.gov"}</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsGpmName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsGpmProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsGpmRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsGpmRole")}</td>
                  <td className="py-3">10.5067/GPM/IMERGDF/DAY/07</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsSmapName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsSmapProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsSmapRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsSmapRole")}</td>
                  <td className="py-3">10.5067/K2VT90DE20GV</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsGraceName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsGraceProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsGraceRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsGraceRole")}</td>
                  <td className="py-3">10.5067/TEMSC-3MJ62</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsNasademName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsNasademProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsNasademRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsNasademRole")}</td>
                  <td className="py-3">10.5067/MEaSUREs/NASADEM.001</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsFirmsName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsFirmsProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsFirmsRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsFirmsRole")}</td>
                  <td className="py-3">10.5067/FIRMS/MODIS</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsHlsName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsHlsProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsHlsRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsHlsRole")}</td>
                  <td className="py-3">10.5067/HLS/HLSL30.002</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsSoilGridsName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsSoilGridsProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsSoilGridsRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsSoilGridsRole")}</td>
                  <td className="py-3">10.5194/soil-7-217-2021</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">{t("methodology.dsMmName")}</td>
                  <td className="py-3 pr-4 text-muted">{t("methodology.dsMmProd")}</td>
                  <td className="py-3 pr-4">{t("methodology.dsMmRes")}</td>
                  <td className="py-3 pr-4 font-sans">{t("methodology.dsMmRole")}</td>
                  <td className="py-3">
                    <a
                      href="https://www.meteomatics.com/en/api/getting-started/"
                      target="_blank"
                      rel="noreferrer"
                      className="underline decoration-dotted hover:text-foreground"
                    >
                      meteomatics.com
                    </a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 2. Process Models */}
        <section className="glass rounded-2xl border border-line overflow-hidden">
          <div className="instrument-header px-6 py-3.5 flex items-center justify-between">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-amber-400" />
              <span>{t("methodology.sec02")}</span>
            </h2>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-emerald-400">
                {t("methodology.m01Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m01Body")}</p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-cyan-400">
                {t("methodology.m02Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m02Body")}</p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-amber-400">
                {t("methodology.m03Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m03Body")}</p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-stone-400">
                {t("methodology.m04Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m04Body")}</p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-emerald-400">
                {t("methodology.m05Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m05Body")}</p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-cyan-400">
                {t("methodology.m06Title")}
              </h3>
              <p className="text-muted leading-relaxed">{t("methodology.m06Body")}</p>
            </div>
          </div>
        </section>

        {/* 3. Climate Safeguards */}
        <section className="glass rounded-2xl border border-line overflow-hidden">
          <div className="instrument-header px-6 py-3.5">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>{t("methodology.sec03")}</span>
            </h2>
          </div>
          <div className="p-6 space-y-3 text-xs text-muted leading-relaxed prose-measure">
            <p>
              <strong className="text-foreground">{t("methodology.sfHeatLabel")}</strong>{" "}
              {t("methodology.sfHeatBody")}
            </p>
            <p>
              <strong className="text-foreground">{t("methodology.sfRainLabel")}</strong>{" "}
              {t("methodology.sfRainBody")}
            </p>
          </div>
        </section>

        {/* 4. Limitations */}
        <section className="rounded-2xl p-6 border border-amber-500/35 bg-amber-500/10 space-y-3">
          <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>{t("methodology.sec04")}</span>
          </h2>
          <ul className="list-disc list-inside space-y-1.5 text-xs text-foreground/85 prose-measure">
            <li>{t("methodology.lim1")}</li>
            <li>{t("methodology.lim2")}</li>
            <li>{t("methodology.lim3")}</li>
            <li>{t("methodology.lim4")}</li>
          </ul>
        </section>
      </div>
    </AppShell>
  );
}
