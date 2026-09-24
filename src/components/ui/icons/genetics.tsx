import { DASHED, Detail, IconBase, type IconProps } from "./IconBase";

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
 *
 * Three turns on a 4.4 pitch, not four on 3.2. At the tighter spacing a front
 * turn's apex passed 0.8 from the back turn behind it — half the width of the
 * two strokes put together — so the aperture filled in and the helix read as a
 * solid ribbon, which is the one thing it cannot be: the gaps between turns are
 * what say "coil" rather than "tube". Each front apex now clears the strand
 * behind it by 1.9.
 */
export function ProteinCodingIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M16 5.6Q12 4 8 10" />
          <path d="M16 10Q12 8.4 8 14.4" />
          <path d="M16 14.4Q12 12.8 8 18.8" />
          <path d="M8 18.8C6.4 19.6 4.6 20.2 2.8 20.6" />
          <path d="M16 5.6C17.6 4 19.4 3.2 21.2 2.8" />
        </>
      }
    >
      <path d="M8 5.6Q12 10 16 5.6" />
      <path d="M8 10Q12 14.4 16 10" />
      <path d="M8 14.4Q12 18.8 16 14.4" />
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
          <path d="M6.6 11.6V8.6H10.2" style={DASHED} />
          <path d="M8.8 7.4L10.4 8.6L8.8 9.8" style={DASHED} />
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

/**
 * The mitochondrial genome.
 *
 * A closed circle, because circularity is what sets a mitogenome apart from a
 * nuclear chromosome at a glance, with its genes as arcs on an inner track in
 * the supporting tone: the way a circular genome map lays out its annotation.
 * The tick through the top of the ring is the control region, where
 * replication starts and numbering begins.
 */
export function MitogenomeIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M13.8 7.1A5.2 5.2 0 0 1 17.2 11.5" />
          <path d="M16.9 13.8A5.2 5.2 0 0 1 11.5 17.2" />
          <path d="M9 16.3A5.2 5.2 0 0 1 7.1 10.2" />
          <path d="M8.3 8.3A5.2 5.2 0 0 1 10.2 7.1" />
        </>
      }
    >
      <circle cx="12" cy="12" r="8.4" />
      <path d="M12 2V5.4" />
    </IconBase>
  );
}

/**
 * A marker sequenced across many individuals — COI, cytb, 12S and the like.
 *
 * One region of a genome rail, boxed and brought forward, with brackets
 * above it for the stretch a primer pair amplifies: a marker is defined by
 * where it sits, not by what it makes.
 */
export function MarkerIcon(props: IconProps) {
  return (
    <IconBase {...props} secondary={<GenomeRail />}>
      <path d="M8.6 12.6H15.4A0.8 0.8 0 0 1 16.2 13.4V16.6A0.8 0.8 0 0 1 15.4 17.4H8.6A0.8 0.8 0 0 1 7.8 16.6V13.4A0.8 0.8 0 0 1 8.6 12.6Z" />
      <path d="M7.8 9.8V7.4H10.2" />
      <path d="M16.2 9.8V7.4H13.8" />
    </IconBase>
  );
}

/**
 * A nuclear genome, drawn as a metaphase chromosome.
 *
 * Two sister chromatids pinched at the centromere: the one shape everyone
 * reads as "chromosome", and so as the nuclear genome rather than the
 * circular mitogenome beside it. The bands across each arm are in the
 * supporting tone, the way a karyotype shows them.
 */
export function ChromosomeIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M7.6 7.4H10.6" />
          <path d="M7.6 16.6H10.6" />
          <path d="M13.4 7.4H16.4" />
          <path d="M13.4 16.6H16.4" />
        </>
      }
    >
      <path d="M9 3.2C7.4 3.2 6.8 4.6 7.2 6.2L9 12L7.2 17.8C6.8 19.4 7.4 20.8 9 20.8C10.4 20.8 11 19.8 11.2 18.4L11.6 12L11.2 5.6C11 4.2 10.4 3.2 9 3.2Z" />
      <path d="M15 3.2C16.6 3.2 17.2 4.6 16.8 6.2L15 12L16.8 17.8C17.2 19.4 16.6 20.8 15 20.8C13.6 20.8 13 19.8 12.8 18.4L12.4 12L12.8 5.6C13 4.2 13.6 3.2 15 3.2Z" />
    </IconBase>
  );
}

/**
 * How an assembly is put together: overlapping contigs, in the supporting
 * tone, joined below into a scaffold whose gaps are the stretches no read
 * spanned. Contig and scaffold N50 measure exactly these two rows.
 */
export function AssemblyIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M3 7H10.4" />
          <path d="M7.6 10H14.6" />
          <path d="M12.4 7H21" />
        </>
      }
    >
      <path d="M3 15.4H9.4" />
      <path d="M11.4 15.4H14.6" />
      <path d="M16.6 15.4H21" />
      <path d="M3 13.6V17.2" />
      <path d="M21 13.6V17.2" />
    </IconBase>
  );
}

/**
 * A genome annotation: genes called on a genome rail, one on each strand,
 * drawn as the arrowed blocks a genome browser uses for features.
 */
export function AnnotationIcon(props: IconProps) {
  return (
    <IconBase {...props} secondary={<GenomeRail />}>
      <path d="M6.2 8.4H10.6L12.4 10.4L10.6 12.4H6.2Z" />
      <path d="M17.8 16.8H13.4L11.6 18.8L13.4 20.8H17.8Z" />
    </IconBase>
  );
}
