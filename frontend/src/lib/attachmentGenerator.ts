import type { ProductAttachmentInput } from "../api/types";

const ATTACHMENT_TEMPLATES = [
  {
    base: "manual_instructions",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Инструкция пользователя и руководство по эксплуатации",
  },
  {
    base: "technical_specs",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Спецификация технических характеристик",
  },
  {
    base: "warranty_certificate",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Гарантийный талон производителя (36 месяцев)",
  },
  {
    base: "product_photo_front",
    ext: "png",
    contentType: "image/png",
    description: "Фотография товара высокого разрешения (вид спереди)",
  },
  {
    base: "product_photo_detail",
    ext: "jpg",
    contentType: "image/jpeg",
    description: "Фотография товара в интерьере / комплектация",
  },
  {
    base: "wiring_diagram",
    ext: "svg",
    contentType: "image/svg+xml",
    description: "Векторная схема подключения и монтажа",
  },
  {
    base: "firmware_update",
    ext: "bin",
    contentType: "application/octet-stream",
    description: "Файл прошивки микроконтроллера (v2.1.0)",
  },
  {
    base: "safety_guidelines",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Сертификат безопасности и правила транспортировки",
  },
  {
    base: "quick_start_guide",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Краткое руководство по быстрому запуску",
  },
  {
    base: "declaration_conformity",
    ext: "pdf",
    contentType: "application/pdf",
    description: "Декларация о соответствии требованиям ЕАЭС",
  },
];

export function generateRandomAttachment(): ProductAttachmentInput {
  const tpl =
    ATTACHMENT_TEMPLATES[Math.floor(Math.random() * ATTACHMENT_TEMPLATES.length)];
  const randomSuffix = Math.floor(100 + Math.random() * 900);
  const filename = `${tpl.base}_${randomSuffix}.${tpl.ext}`;
  const randomSize = Math.floor(1024 * (15 + Math.random() * 4096)); // 15 КБ - 4 МБ

  // 16-hex characters fake sha256 prefix
  const fakeHash = Array.from({ length: 16 }, () =>
    Math.floor(Math.random() * 16).toString(16),
  ).join("");

  return {
    filename,
    content_type: tpl.contentType,
    size_bytes: randomSize,
    order: 0,
    checksum: `sha256:${fakeHash}`,
    description: tpl.description,
  };
}
