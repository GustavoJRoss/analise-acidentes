/** Remove acentos para buscas: "florianópolis" casa com "florianopolis". */
export function semAcentos(texto: string) {
  return texto.normalize("NFD").replace(/\p{Diacritic}/gu, "");
}
