import { Detail, IconBase, type IconProps } from "./IconBase";

// ---------------------------------------------------------------------------
// Three of these are drawn as molecules and one — the pseudogene — as an
// annotation on a genome rail, the way a genome browser draws a track. That is
// the right split: the other three cards count molecules that exist, and a
// pseudogene is defined by what is wrong with the locus rather than by any
// product, because it has none.
// ---------------------------------------------------------------------------

function GenomeRail() {
  return (
    <>
      <path d="M2.2 15H21.8" />
      <path d="M3.4 13.4V16.6" />
      <path d="M5.2 13.4V16.6" />
      <path d="M18.8 13.4V16.6" />
      <path d="M20.6 13.4V16.6" />
    </>
  );
}

/**
 * Protein-coding genes.
 *
 * The folded product rather than the annotated gene: an alpha helix, with the
 * unfolded polypeptide chain running in at one end and out at the other. The
 * helix is the one protein motif that is recognisable at icon size, and
 * "codes for a protein" is what the count on this card actually means.
 *
 * Front turns are the subject; the stretches passing behind the axis carry the
 * supporting tone, which is what gives the coil depth without an opaque
 * knockout stroke — the same trick the DNA glyph uses at its crossings.
 */
export function ProteinCodingIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M16 6.6Q12 6 8 9.8" />
          <path d="M16 9.8Q12 9.2 8 13" />
          <path d="M16 13Q12 12.4 8 16.2" />
          <path d="M8 17.4C6.4 19 4.6 20 2.8 20.6" />
          <path d="M16 6.6C17.6 4.8 19.4 3.8 21.2 3.4" />
        </>
      }
    >
      <path d="M8 6.6Q12 9.2 16 6.6" />
      <path d="M8 9.8Q12 12.4 16 9.8" />
      <path d="M8 13Q12 15.6 16 13" />
      <path d="M8 16.2Q12 18.8 16 16.2" />
    </IconBase>
  );
}

/**
 * RNA genes — rRNA, tRNA, ncRNA and the rest.
 *
 * A single strand folded back on itself into a stem-loop. Single-strandedness
 * with self-pairing secondary structure is the one unambiguous "this is RNA"
 * visual; a double helix here is the commonest mistake in RNA icons, and it
 * would make this indistinguishable from the generic DNA glyph sitting beside
 * it in the same grid.
 */
export function RnaIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M9.5 13.6H14.5" />
          <path d="M9.3 16.2H14.7" />
          <path d="M9.1 18.8H14.9" />
          <path d="M15.1 20.8C16.6 21.4 18.4 20.8 19.6 19.6" />
        </>
      }
    >
      <path d="M8.9 20.8C8.7 17.4 9 14.4 9.8 11.8C7.8 9.4 8.6 5.6 12 4.8C15.4 5.6 16.2 9.4 14.2 11.8C15 14.4 15.3 17.4 15.1 20.8" />
    </IconBase>
  );
}

/**
 * Pseudogenes.
 *
 * An open reading frame on a genome rail, broken: split by a gap with a
 * deletion caret over it, and the start arrow it once carried now a dashed
 * ghost with a strike through it.
 *
 * Loss of the start codon and a disrupted reading frame are what define a
 * pseudogene, and "was functional, now isn't" is a statement the two-tone
 * system can make that a single tone cannot.
 */
export function PseudoGeneIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <GenomeRail />
          <path d="M6.6 11.6V8.6H10.2" strokeDasharray="1.5 1.4" />
          <path d="M8.8 7.4L10.4 8.6L8.8 9.8" strokeDasharray="1.5 1.4" />
        </>
      }
    >
      <path d="M10.6 11.6H7.8A1.2 1.2 0 0 0 6.6 12.8V17.2A1.2 1.2 0 0 0 7.8 18.4H10.6" />
      <path d="M13.4 11.6H16.2A1.2 1.2 0 0 1 17.4 12.8V17.2A1.2 1.2 0 0 1 16.2 18.4H13.4" />
      <path d="M10.6 10.2L12 7.6L13.4 10.2" />
      <path d="M5.2 11L11.6 6.4" />
    </IconBase>
  );
}

/**
 * Everything else — the generic gene.
 *
 * A double helix, with the rear strand in the supporting tone. That solves the
 * occlusion at each crossing with the colour system itself rather than with an
 * opaque knockout stroke, and the rungs shorten as the strands converge, which
 * is the foreshortening that separates a helix from a twisted ladder.
 */
export function DnaIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <path d="M15.6 3C15.6 5.4 8.4 6.6 8.4 9C8.4 11.4 15.6 12.6 15.6 15C15.6 17.4 8.4 18.6 8.4 21" />
      }
    >
      <path d="M8.4 3C8.4 5.4 15.6 6.6 15.6 9C15.6 11.4 8.4 12.6 8.4 15C8.4 17.4 15.6 18.6 15.6 21" />
      <Detail>
        <path d="M8.4 3H15.6" />
        <path d="M10.4 5.1H13.6" />
        <path d="M8.4 9H15.6" />
        <path d="M10.4 11.1H13.6" />
        <path d="M8.4 15H15.6" />
        <path d="M10.4 17.1H13.6" />
        <path d="M8.4 21H15.6" />
      </Detail>
    </IconBase>
  );
}
